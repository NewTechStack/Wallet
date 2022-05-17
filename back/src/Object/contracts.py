from web3 import Web3, exceptions, middleware
from web3.middleware import geth_poa_middleware
from web3.gas_strategies.time_based import construct_time_based_gas_price_strategy
from hexbytes import HexBytes
import requests
import os
import decimal
import json
try:
    from .rethink import get_conn, r
except:
    pass

mnemonic = str(os.getenv('MNEMONIC', ''))

class W3:
    def __init__(self, network_type = 'polygon', network = 'testnet'):
        self.networks = {
            "polygon": {
                "mainnet": {
                    "rpc": "https://polygon-rpc.com",
                    "explorer": {
                        "url": "https://polygonscan.com/",
                        "transaction": "tx",
                        "address": "address",
                        },
                },
                "testnet": {
                    "rpc": "https://rpc-mumbai.matic.today",
                    "explorer": {
                        "url": "https://mumbai.polygonscan.com/",
                        "transaction": "tx",
                        "address": "address",
                        }
                }
            },
            "ether": {
                "testnet": {
                    "rpc": "https://ropsten.infura.io/v3/9aa3d95b3bc440fa88ea12eaa4456161",
                    "explorer": {
                        "url": "https://ropsten.etherscan.io/",
                        "transaction": "tx",
                        "address": "address",
                    }
                }

            }
        }
        self.network_type = 'polygon' if network_type == None else network_type
        self.network = 'testnet' if network == None else network
        self.link = Web3()
        self.unit = 'ETH' if self.network_type == 'ether' else 'MATIC' if self.network_type == 'polygon' else ''


    def is_connected(self):
        return self.link.isConnected()

    def connect(self, network_type = None, network = None):
        self.network_type = network_type if network_type != None else self.network_type
        self.network = network if network != None else self.network
        if self.network_type not in self.networks \
            or self.network not in self.networks[self.network_type]:
            return [False, "invalid connection argument", 400]
        provider = self.networks[self.network_type][self.network]['rpc']
        self.link = Web3(Web3.HTTPProvider(provider))
        self.link.middleware_onion.inject(geth_poa_middleware, layer=0)
        self.link.eth.account.enable_unaudited_hdwallet_features()
        self.unit = 'ETH' if self.network_type == 'ether' else 'MATIC' if self.network_type == 'polygon' else ''
        return [True, f"Connected to {provider}", None]

    def execute_transaction(self, transaction, owner_address, owner_key, mult_gas = 2, wait = True):
        gas_cost = None
        for _ in range(10):
            try:
                gas_cost = transaction.estimateGas({'from': owner_address})
                break
            except exceptions.ContractLogicError:
                pass
        if gas_cost is None:
            return [False, "Invalid logic", 400]
        build = None
        gas_price = self.link.eth.generate_gas_price() * mult_gas
        for _ in range(10):
            try:
                build = transaction.buildTransaction({
                  'from': owner_address,
                  'gas': gas_cost,
                  'gasPrice': gas_price,
                  'nonce': self.link.eth.getTransactionCount(owner_address, "pending")
                })
            except requests.exceptions.HTTPError:
                pass
        if build is None:
            return [False, "Can't connect to RPC", 404]
        signed_txn = self.link.eth.account.signTransaction(build, private_key=owner_key)
        txn = self.link.eth.sendRawTransaction(signed_txn.rawTransaction).hex()
        txn_receipt = None
        if wait is True:
            for _ in range(10):
                try:
                    txn_receipt = dict(self.link.eth.waitForTransactionReceipt(txn))
                    break
                except exceptions.TimeExhausted:
                    pass
        if txn_receipt is None:
            return [True, {"transact": txn}, None]
        del txn_receipt['logs']
        del txn_receipt['logsBloom']
        txn_receipt = self.hextojson(txn_receipt)
        return [True, {"transact": txn, 'return': txn_receipt}, None]

    def hextojson(self, data):
        class HexJsonEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, HexBytes):
                    return obj.hex()
                if isinstance(obj, decimal.Decimal):
                    return float(obj)
                if isinstance(obj, bytes):
                    return [obj.decode("utf-8", errors='ignore'), str(obj)]
                return super().default(obj)
        return json.loads(json.dumps(dict(data), cls=HexJsonEncoder))

    def owner(self):
        return self.link.eth.account.from_mnemonic(mnemonic)

    def status(self):
        block = self.link.eth.get_block('latest')
        ret = self.hextojson(block)
        return [True, {'data': ret}, None]

class Contract(W3):
    def __init__(self, address, network_type = None, network = None):
        super().__init__(network_type = network_type, network = network)
        self.address = None
        try:
            self.address = self.link.toChecksumAddress(address)
        except:
            pass
        self.abi = []
        self.bytecode = ""
        try:
            self.red = get_conn().db("wallet").table('contracts')
            self.trx = get_conn().db("wallet").table('transactions')
        except:
            self.red = None
            self.trx = None

    def get_functions(self, id):
        contract = dict(self.red.get(id).run())
        functions = contract["deployment_infos"]["functions"]
        return [True, functions, None]

    def get_transaction(self, id):
        contract = dict(self.red.get(id).run())
        address = contract["address"]
        transactions = list(self.trx.filter(
                (r.row["address"] == address)
                & (r.row["type"] == 'contract')
            ).run())
        return [True, transactions, None]

    def exec_function(self, name, kwargs, wait=True):
        keep_function = None
        for function in self.abi:
            if 'type' in function and function['type'] == 'function':
                if 'name' in function and function['name'] == name:
                    keep_function = function
        if keep_function is None:
            return [False, "Invalid function name", 400]
        elem_kwargs = []
        for elem in keep_function['inputs']:
            elem_name = elem['name']
            elem_type = elem['type']
            elem_kwargs.append(elem['name'])
            if elem_name not in kwargs:
                return [False, f"missing {elem_name}:{elem_type}", 400]
        contract = self.link.eth.contract(self.address, abi=self.abi)
        transaction = contract.get_function_by_name(name)(**{name: kwargs[name] for name in elem_kwargs})
        if keep_function['stateMutability'] == 'view':
            return [True, self.hextojson({'result': transaction.call()}), None]
        owner = self.owner()
        return self.execute_transaction(transaction, owner.address, owner.key, wait)

    def get_constructor(self):
        constructor = [i for i in self.abi if 'type' in i and i['type'] == 'constructor']
        if len(constructor) > 0:
            constructor = constructor[0]['inputs']
        return [True, constructor, None]

    def __get_simplified(self, type):
        simplified = {}
        hash = {}
        for func in [obj for obj in self.abi if obj['type'] == type]:
            name = func['name'] if 'name' in func else type
            types = [input['type'] for input in func['inputs']]
            args = [input['name'] + '(' + input['type'] + ')' for input in func['inputs']]
            signature = '{}({})'.format(name,','.join(types))
            simple = '{}({})'.format(name,','.join(args))
            simplified[name] = simple
            hash[name] = self.link.toHex(self.link.keccak(text=signature))[0:10]
        return {"clear": simplified, "hash": hash}

    def deploy(self, kwargs, metadata = {}):
        owner = self.owner()
        constructor = [i for i in self.abi if 'type' in i and i['type'] == 'constructor']
        if len(constructor) == 0:
            return [False, "can't deploy that contract", 400]
        if not isinstance(metadata, dict):
            return [False, "Invalid metadata", 400]
        constructor = constructor[0]['inputs']
        for elem in constructor:
            name = elem['name']
            type = elem['type']
            if name == 'owner':
                kwargs['owner'] = owner.address
            elif name not in kwargs:
                return [False, f"missing {name}:{type}", 400]
        contract = self.link.eth.contract(abi=self.abi, bytecode=self.bytecode)
        transaction = contract.constructor(**kwargs)
        ret = self.execute_transaction(transaction, owner.address, owner.key, mult_gas = 3)
        if not ret[0]:
            return ret
        if 'return' not in ret[1]:
            ret[1]['return'] = dict(self.link.eth.waitForTransactionReceipt(txn))
        data = {
            'deployment_infos': {
                "log": ret[1],
                "abi": self.abi,
                "bytecode": self.bytecode,
                "functions": self.__get_simplified('function'),
                "constructor": self.__get_simplified('constructor')
            },
            "metadata": metadata,
            "owner": owner.address,
            "network_type": self.network_type,
            "network": self.network,
            "address": ret[1]['return']['contractAddress'],
        }
        res = dict(self.red.insert([data]).run())
        id = res["generated_keys"][0]
        return [True, {"id": id} , None]

    def get_contract(self, id, expand):
        command =  self.red
        if id is not None:
            command = command.filter(r.row["id"] == id)
        contracts = command.run()
        contracts = list(contracts)
        if len(contracts) == 0 and id is not None:
            return [False, "invalid contract id", 404]
        for contract in contracts:
            del contract['deployment_infos']['bytecode']
            del contract['deployment_infos']['abi']
            if expand is False:
                del contract['deployment_infos']['log']
        return [True, contracts, None]

    def internal_get_contract(self, id):
        contract = self.red.get(id).run()
        if contract is None:
            return [False, "invalid contract id", 404]
        contract = dict(contract)
        abi = contract['deployment_infos']['abi']
        bytecode = contract['deployment_infos']['bytecode']
        address = contract['address']
        network_type = contract['network_type']
        network = contract['network']
        return [True, ERCX(address, abi, bytecode, network_type, network), None]

class ERCX(Contract):
    def __init__(self, address,  abi, bytecode, network_type = None, network = None):
         super().__init__(address, network_type = network_type, network = network)
         self.bytecode = bytecode
         self.abi = abi

class Erc20(Contract):
    def __init__(self, address,  network_type = None, network = None):
         super().__init__(address, network_type = network_type, network = network)
         self.bytecode = "0x60806040523480156200001157600080fd5b5060405162001a0038038062001a00833981810160405260808110156200003757600080fd5b81019080805160405193929190846401000000008211156200005857600080fd5b838201915060208201858111156200006f57600080fd5b82518660018202830111640100000000821117156200008d57600080fd5b8083526020830192505050908051906020019080838360005b83811015620000c3578082015181840152602081019050620000a6565b50505050905090810190601f168015620000f15780820380516001836020036101000a031916815260200191505b50604052602001805160405193929190846401000000008211156200011557600080fd5b838201915060208201858111156200012c57600080fd5b82518660018202830111640100000000821117156200014a57600080fd5b8083526020830192505050908051906020019080838360005b838110156200018057808201518184015260208101905062000163565b50505050905090810190601f168015620001ae5780820380516001836020036101000a031916815260200191505b50604052602001805190602001909291908051906020019092919050505083838160039080519060200190620001e6929190620004a6565b508060049080519060200190620001ff929190620004a6565b506012600560006101000a81548160ff021916908360ff16021790555050506200023081836200023a60201b60201c565b505050506200054c565b600073ffffffffffffffffffffffffffffffffffffffff168273ffffffffffffffffffffffffffffffffffffffff161415620002de576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040180806020018281038252601f8152602001807f45524332303a206d696e7420746f20746865207a65726f20616464726573730081525060200191505060405180910390fd5b620002f2600083836200041860201b60201c565b6200030e816002546200041d60201b62000ab81790919060201c565b6002819055506200036c816000808573ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff168152602001908152602001600020546200041d60201b62000ab81790919060201c565b6000808473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff168152602001908152602001600020819055508173ffffffffffffffffffffffffffffffffffffffff16600073ffffffffffffffffffffffffffffffffffffffff167fddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef836040518082815260200191505060405180910390a35050565b505050565b6000808284019050838110156200049c576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040180806020018281038252601b8152602001807f536166654d6174683a206164646974696f6e206f766572666c6f77000000000081525060200191505060405180910390fd5b8091505092915050565b828054600181600116156101000203166002900490600052602060002090601f016020900481019282601f10620004e957805160ff19168380011785556200051a565b828001600101855582156200051a579182015b8281111562000519578251825591602001919060010190620004fc565b5b5090506200052991906200052d565b5090565b5b80821115620005485760008160009055506001016200052e565b5090565b6114a4806200055c6000396000f3fe608060405234801561001057600080fd5b50600436106100cf5760003560e01c806342966c681161008c57806395d89b411161006657806395d89b41146103b6578063a457c2d714610439578063a9059cbb1461049d578063dd62ed3e14610501576100cf565b806342966c68146102e257806370a082311461031057806379cc679014610368576100cf565b806306fdde03146100d4578063095ea7b31461015757806318160ddd146101bb57806323b872dd146101d9578063313ce5671461025d578063395093511461027e575b600080fd5b6100dc610579565b6040518080602001828103825283818151815260200191508051906020019080838360005b8381101561011c578082015181840152602081019050610101565b50505050905090810190601f1680156101495780820380516001836020036101000a031916815260200191505b509250505060405180910390f35b6101a36004803603604081101561016d57600080fd5b81019080803573ffffffffffffffffffffffffffffffffffffffff1690602001909291908035906020019092919050505061061b565b60405180821515815260200191505060405180910390f35b6101c3610639565b6040518082815260200191505060405180910390f35b610245600480360360608110156101ef57600080fd5b81019080803573ffffffffffffffffffffffffffffffffffffffff169060200190929190803573ffffffffffffffffffffffffffffffffffffffff16906020019092919080359060200190929190505050610643565b60405180821515815260200191505060405180910390f35b61026561071c565b604051808260ff16815260200191505060405180910390f35b6102ca6004803603604081101561029457600080fd5b81019080803573ffffffffffffffffffffffffffffffffffffffff16906020019092919080359060200190929190505050610733565b60405180821515815260200191505060405180910390f35b61030e600480360360208110156102f857600080fd5b81019080803590602001909291905050506107e6565b005b6103526004803603602081101561032657600080fd5b81019080803573ffffffffffffffffffffffffffffffffffffffff1690602001909291905050506107fa565b6040518082815260200191505060405180910390f35b6103b46004803603604081101561037e57600080fd5b81019080803573ffffffffffffffffffffffffffffffffffffffff16906020019092919080359060200190929190505050610842565b005b6103be6108a4565b6040518080602001828103825283818151815260200191508051906020019080838360005b838110156103fe5780820151818401526020810190506103e3565b50505050905090810190601f16801561042b5780820380516001836020036101000a031916815260200191505b509250505060405180910390f35b6104856004803603604081101561044f57600080fd5b81019080803573ffffffffffffffffffffffffffffffffffffffff16906020019092919080359060200190929190505050610946565b60405180821515815260200191505060405180910390f35b6104e9600480360360408110156104b357600080fd5b81019080803573ffffffffffffffffffffffffffffffffffffffff16906020019092919080359060200190929190505050610a13565b60405180821515815260200191505060405180910390f35b6105636004803603604081101561051757600080fd5b81019080803573ffffffffffffffffffffffffffffffffffffffff169060200190929190803573ffffffffffffffffffffffffffffffffffffffff169060200190929190505050610a31565b6040518082815260200191505060405180910390f35b606060038054600181600116156101000203166002900480601f0160208091040260200160405190810160405280929190818152602001828054600181600116156101000203166002900480156106115780601f106105e657610100808354040283529160200191610611565b820191906000526020600020905b8154815290600101906020018083116105f457829003601f168201915b5050505050905090565b600061062f610628610b40565b8484610b48565b6001905092915050565b6000600254905090565b6000610650848484610d3f565b6107118461065c610b40565b61070c8560405180606001604052806028815260200161139460289139600160008b73ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060006106c2610b40565b73ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff168152602001908152602001600020546110009092919063ffffffff16565b610b48565b600190509392505050565b6000600560009054906101000a900460ff16905090565b60006107dc610740610b40565b846107d78560016000610751610b40565b73ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060008973ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002054610ab890919063ffffffff16565b610b48565b6001905092915050565b6107f76107f1610b40565b826110ba565b50565b60008060008373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff168152602001908152602001600020549050919050565b6000610881826040518060600160405280602481526020016113bc602491396108728661086d610b40565b610a31565b6110009092919063ffffffff16565b90506108958361088f610b40565b83610b48565b61089f83836110ba565b505050565b606060048054600181600116156101000203166002900480601f01602080910402602001604051908101604052809291908181526020018280546001816001161561010002031660029004801561093c5780601f106109115761010080835404028352916020019161093c565b820191906000526020600020905b81548152906001019060200180831161091f57829003601f168201915b5050505050905090565b6000610a09610953610b40565b84610a048560405180606001604052806025815260200161144a602591396001600061097d610b40565b73ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060008a73ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff168152602001908152602001600020546110009092919063ffffffff16565b610b48565b6001905092915050565b6000610a27610a20610b40565b8484610d3f565b6001905092915050565b6000600160008473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060008373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002054905092915050565b600080828401905083811015610b36576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040180806020018281038252601b8152602001807f536166654d6174683a206164646974696f6e206f766572666c6f77000000000081525060200191505060405180910390fd5b8091505092915050565b600033905090565b600073ffffffffffffffffffffffffffffffffffffffff168373ffffffffffffffffffffffffffffffffffffffff161415610bce576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260248152602001806114266024913960400191505060405180910390fd5b600073ffffffffffffffffffffffffffffffffffffffff168273ffffffffffffffffffffffffffffffffffffffff161415610c54576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040180806020018281038252602281526020018061134c6022913960400191505060405180910390fd5b80600160008573ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060008473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff168152602001908152602001600020819055508173ffffffffffffffffffffffffffffffffffffffff168373ffffffffffffffffffffffffffffffffffffffff167f8c5be1e5ebec7d5bd14f71427d1e84f3dd0314c0f7b2291e5b200ac8c7c3b925836040518082815260200191505060405180910390a3505050565b600073ffffffffffffffffffffffffffffffffffffffff168373ffffffffffffffffffffffffffffffffffffffff161415610dc5576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260258152602001806114016025913960400191505060405180910390fd5b600073ffffffffffffffffffffffffffffffffffffffff168273ffffffffffffffffffffffffffffffffffffffff161415610e4b576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260238152602001806113076023913960400191505060405180910390fd5b610e5683838361127e565b610ec18160405180606001604052806026815260200161136e602691396000808773ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff168152602001908152602001600020546110009092919063ffffffff16565b6000808573ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002081905550610f54816000808573ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002054610ab890919063ffffffff16565b6000808473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff168152602001908152602001600020819055508173ffffffffffffffffffffffffffffffffffffffff168373ffffffffffffffffffffffffffffffffffffffff167fddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef836040518082815260200191505060405180910390a3505050565b60008383111582906110ad576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825283818151815260200191508051906020019080838360005b83811015611072578082015181840152602081019050611057565b50505050905090810190601f16801561109f5780820380516001836020036101000a031916815260200191505b509250505060405180910390fd5b5082840390509392505050565b600073ffffffffffffffffffffffffffffffffffffffff168273ffffffffffffffffffffffffffffffffffffffff161415611140576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260218152602001806113e06021913960400191505060405180910390fd5b61114c8260008361127e565b6111b78160405180606001604052806022815260200161132a602291396000808673ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff168152602001908152602001600020546110009092919063ffffffff16565b6000808473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1681526020019081526020016000208190555061120e8160025461128390919063ffffffff16565b600281905550600073ffffffffffffffffffffffffffffffffffffffff168273ffffffffffffffffffffffffffffffffffffffff167fddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef836040518082815260200191505060405180910390a35050565b505050565b6000828211156112fb576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040180806020018281038252601e8152602001807f536166654d6174683a207375627472616374696f6e206f766572666c6f77000081525060200191505060405180910390fd5b81830390509291505056fe45524332303a207472616e7366657220746f20746865207a65726f206164647265737345524332303a206275726e20616d6f756e7420657863656564732062616c616e636545524332303a20617070726f766520746f20746865207a65726f206164647265737345524332303a207472616e7366657220616d6f756e7420657863656564732062616c616e636545524332303a207472616e7366657220616d6f756e74206578636565647320616c6c6f77616e636545524332303a206275726e20616d6f756e74206578636565647320616c6c6f77616e636545524332303a206275726e2066726f6d20746865207a65726f206164647265737345524332303a207472616e736665722066726f6d20746865207a65726f206164647265737345524332303a20617070726f76652066726f6d20746865207a65726f206164647265737345524332303a2064656372656173656420616c6c6f77616e63652062656c6f77207a65726fa2646970667358221220ea8921b12623c1150abb5ad231a6e6344c748fe8ee89e35829a9d9077bb3ce3964736f6c634300060c0033"
         self.abi = [
                    	{
                    		"inputs": [
                    			{
                    				"internalType": "string",
                    				"name": "name",
                    				"type": "string"
                    			},
                    			{
                    				"internalType": "string",
                    				"name": "symbol",
                    				"type": "string"
                    			},
                    			{
                    				"internalType": "uint256",
                    				"name": "initialSupply",
                    				"type": "uint256"
                    			},
                    			{
                    				"internalType": "address",
                    				"name": "owner",
                    				"type": "address"
                    			}
                    		],
                    		"stateMutability": "nonpayable",
                    		"type": "constructor"
                    	},
                    	{
                    		"anonymous": False,
                    		"inputs": [
                    			{
                    				"indexed": True,
                    				"internalType": "address",
                    				"name": "owner",
                    				"type": "address"
                    			},
                    			{
                    				"indexed": True,
                    				"internalType": "address",
                    				"name": "spender",
                    				"type": "address"
                    			},
                    			{
                    				"indexed": False,
                    				"internalType": "uint256",
                    				"name": "value",
                    				"type": "uint256"
                    			}
                    		],
                    		"name": "Approval",
                    		"type": "event"
                    	},
                    	{
                    		"anonymous": False,
                    		"inputs": [
                    			{
                    				"indexed": True,
                    				"internalType": "address",
                    				"name": "from",
                    				"type": "address"
                    			},
                    			{
                    				"indexed": True,
                    				"internalType": "address",
                    				"name": "to",
                    				"type": "address"
                    			},
                    			{
                    				"indexed": False,
                    				"internalType": "uint256",
                    				"name": "value",
                    				"type": "uint256"
                    			}
                    		],
                    		"name": "Transfer",
                    		"type": "event"
                    	},
                    	{
                    		"inputs": [
                    			{
                    				"internalType": "address",
                    				"name": "owner",
                    				"type": "address"
                    			},
                    			{
                    				"internalType": "address",
                    				"name": "spender",
                    				"type": "address"
                    			}
                    		],
                    		"name": "allowance",
                    		"outputs": [
                    			{
                    				"internalType": "uint256",
                    				"name": "",
                    				"type": "uint256"
                    			}
                    		],
                    		"stateMutability": "view",
                    		"type": "function"
                    	},
                    	{
                    		"inputs": [
                    			{
                    				"internalType": "address",
                    				"name": "spender",
                    				"type": "address"
                    			},
                    			{
                    				"internalType": "uint256",
                    				"name": "amount",
                    				"type": "uint256"
                    			}
                    		],
                    		"name": "approve",
                    		"outputs": [
                    			{
                    				"internalType": "bool",
                    				"name": "",
                    				"type": "bool"
                    			}
                    		],
                    		"stateMutability": "nonpayable",
                    		"type": "function"
                    	},
                    	{
                    		"inputs": [
                    			{
                    				"internalType": "address",
                    				"name": "account",
                    				"type": "address"
                    			}
                    		],
                    		"name": "balanceOf",
                    		"outputs": [
                    			{
                    				"internalType": "uint256",
                    				"name": "",
                    				"type": "uint256"
                    			}
                    		],
                    		"stateMutability": "view",
                    		"type": "function"
                    	},
                    	{
                    		"inputs": [
                    			{
                    				"internalType": "uint256",
                    				"name": "amount",
                    				"type": "uint256"
                    			}
                    		],
                    		"name": "burn",
                    		"outputs": [],
                    		"stateMutability": "nonpayable",
                    		"type": "function"
                    	},
                    	{
                    		"inputs": [
                    			{
                    				"internalType": "address",
                    				"name": "account",
                    				"type": "address"
                    			},
                    			{
                    				"internalType": "uint256",
                    				"name": "amount",
                    				"type": "uint256"
                    			}
                    		],
                    		"name": "burnFrom",
                    		"outputs": [],
                    		"stateMutability": "nonpayable",
                    		"type": "function"
                    	},
                    	{
                    		"inputs": [],
                    		"name": "decimals",
                    		"outputs": [
                    			{
                    				"internalType": "uint8",
                    				"name": "",
                    				"type": "uint8"
                    			}
                    		],
                    		"stateMutability": "view",
                    		"type": "function"
                    	},
                    	{
                    		"inputs": [
                    			{
                    				"internalType": "address",
                    				"name": "spender",
                    				"type": "address"
                    			},
                    			{
                    				"internalType": "uint256",
                    				"name": "subtractedValue",
                    				"type": "uint256"
                    			}
                    		],
                    		"name": "decreaseAllowance",
                    		"outputs": [
                    			{
                    				"internalType": "bool",
                    				"name": "",
                    				"type": "bool"
                    			}
                    		],
                    		"stateMutability": "nonpayable",
                    		"type": "function"
                    	},
                    	{
                    		"inputs": [
                    			{
                    				"internalType": "address",
                    				"name": "spender",
                    				"type": "address"
                    			},
                    			{
                    				"internalType": "uint256",
                    				"name": "addedValue",
                    				"type": "uint256"
                    			}
                    		],
                    		"name": "increaseAllowance",
                    		"outputs": [
                    			{
                    				"internalType": "bool",
                    				"name": "",
                    				"type": "bool"
                    			}
                    		],
                    		"stateMutability": "nonpayable",
                    		"type": "function"
                    	},
                    	{
                    		"inputs": [],
                    		"name": "name",
                    		"outputs": [
                    			{
                    				"internalType": "string",
                    				"name": "",
                    				"type": "string"
                    			}
                    		],
                    		"stateMutability": "view",
                    		"type": "function"
                    	},
                    	{
                    		"inputs": [],
                    		"name": "symbol",
                    		"outputs": [
                    			{
                    				"internalType": "string",
                    				"name": "",
                    				"type": "string"
                    			}
                    		],
                    		"stateMutability": "view",
                    		"type": "function"
                    	},
                    	{
                    		"inputs": [],
                    		"name": "totalSupply",
                    		"outputs": [
                    			{
                    				"internalType": "uint256",
                    				"name": "",
                    				"type": "uint256"
                    			}
                    		],
                    		"stateMutability": "view",
                    		"type": "function"
                    	},
                    	{
                    		"inputs": [
                    			{
                    				"internalType": "address",
                    				"name": "recipient",
                    				"type": "address"
                    			},
                    			{
                    				"internalType": "uint256",
                    				"name": "amount",
                    				"type": "uint256"
                    			}
                    		],
                    		"name": "transfer",
                    		"outputs": [
                    			{
                    				"internalType": "bool",
                    				"name": "",
                    				"type": "bool"
                    			}
                    		],
                    		"stateMutability": "nonpayable",
                    		"type": "function"
                    	},
                    	{
                    		"inputs": [
                    			{
                    				"internalType": "address",
                    				"name": "sender",
                    				"type": "address"
                    			},
                    			{
                    				"internalType": "address",
                    				"name": "recipient",
                    				"type": "address"
                    			},
                    			{
                    				"internalType": "uint256",
                    				"name": "amount",
                    				"type": "uint256"
                    			}
                    		],
                    		"name": "transferFrom",
                    		"outputs": [
                    			{
                    				"internalType": "bool",
                    				"name": "",
                    				"type": "bool"
                    			}
                    		],
                    		"stateMutability": "nonpayable",
                    		"type": "function"
                    	}
                    ]


class Erc721(Contract):
    def __init__(self, address,  network_type = None, network = None):
         super().__init__(address, network_type = network_type, network = network)
         self.bytecode = "60806040523480156200001157600080fd5b5060405162004a3538038062004a35833981810160405260608110156200003757600080fd5b81019080805160405193929190846401000000008211156200005857600080fd5b838201915060208201858111156200006f57600080fd5b82518660018202830111640100000000821117156200008d57600080fd5b8083526020830192505050908051906020019080838360005b83811015620000c3578082015181840152602081019050620000a6565b50505050905090810190601f168015620000f15780820380516001836020036101000a031916815260200191505b50604052602001805160405193929190846401000000008211156200011557600080fd5b838201915060208201858111156200012c57600080fd5b82518660018202830111640100000000821117156200014a57600080fd5b8083526020830192505050908051906020019080838360005b838110156200018057808201518184015260208101905062000163565b50505050905090810190601f168015620001ae5780820380516001836020036101000a031916815260200191505b5060405260200180516040519392919084640100000000821115620001d257600080fd5b83820191506020820185811115620001e957600080fd5b82518660018202830111640100000000821117156200020757600080fd5b8083526020830192505050908051906020019080838360005b838110156200023d57808201518184015260208101905062000220565b50505050905090810190601f1680156200026b5780820380516001836020036101000a031916815260200191505b5060405250505033600360006101000a81548173ffffffffffffffffffffffffffffffffffffffff021916908373ffffffffffffffffffffffffffffffffffffffff160217905550620002c4336200033360201b60201c565b6000600560006101000a81548160ff0219169083151502179055508260069080519060200190620002f792919062000558565b5081600790805190602001906200031092919062000558565b5080600890805190602001906200032992919062000558565b5050505062000607565b6200034e8160046200039460201b620040c61790919060201c565b8073ffffffffffffffffffffffffffffffffffffffff167f6719d08c1888103bea251a4ed56406bd0c3e69723c8a1686e017e7bbe159b6f860405160405180910390a250565b620003a682826200047860201b60201c565b156200041a576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040180806020018281038252601f8152602001807f526f6c65733a206163636f756e7420616c72656164792068617320726f6c650081525060200191505060405180910390fd5b60018260000160008373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060006101000a81548160ff0219169083151502179055505050565b60008073ffffffffffffffffffffffffffffffffffffffff168273ffffffffffffffffffffffffffffffffffffffff16141562000501576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040180806020018281038252602281526020018062004a136022913960400191505060405180910390fd5b8260000160008373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060009054906101000a900460ff16905092915050565b828054600181600116156101000203166002900490600052602060002090601f016020900481019282601f106200059b57805160ff1916838001178555620005cc565b82800160010185558215620005cc579182015b82811115620005cb578251825591602001919060010190620005ae565b5b509050620005db9190620005df565b5090565b6200060491905b8082111562000600576000816000905550600101620005e6565b5090565b90565b6143fc80620006176000396000f3fe608060405234801561001057600080fd5b50600436106101fb5760003560e01c80638140d0dc1161011a578063c6786e5a116100ad578063dd62ed3e1161007c578063dd62ed3e14610b16578063e46638e614610b8e578063f0eb5e5414610c14578063f2fde38b14610cd1578063fcf196b414610d15576101fb565b8063c6786e5a146109b9578063cc872b6614610a32578063d4ce141514610a60578063db006a7514610ae8576101fb565b806395d89b41116100e957806395d89b4114610826578063a457c2d7146108a9578063a4a0a3011461090f578063a9059cbb14610953576101fb565b80638140d0dc1461071557806382dc1ec41461078e5780638456cb59146107d25780638da5cb5b146107dc576101fb565b806346fbf68e116101925780636ef8d66d116101615780636ef8d66d146105ff57806370a0823114610609578063715018a6146106615780637f4ab1dd1461066b576101fb565b806346fbf68e146104a45780635c975abb146105005780635fff8cd314610522578063630e327d14610586576101fb565b8063313ce567116101ce578063313ce5671461038d57806333a8c45a146103b157806339509351146104345780633f4ba83a1461049a576101fb565b806306fdde0314610200578063095ea7b31461028357806318160ddd146102e957806323b872dd14610307575b600080fd5b610208610d5f565b6040518080602001828103825283818151815260200191508051906020019080838360005b8381101561024857808201518184015260208101905061022d565b50505050905090810190601f1680156102755780820380516001836020036101000a031916815260200191505b509250505060405180910390f35b6102cf6004803603604081101561029957600080fd5b81019080803573ffffffffffffffffffffffffffffffffffffffff16906020019092919080359060200190929190505050610dfd565b604051808215151515815260200191505060405180910390f35b6102f1610e94565b6040518082815260200191505060405180910390f35b6103736004803603606081101561031d57600080fd5b81019080803573ffffffffffffffffffffffffffffffffffffffff169060200190929190803573ffffffffffffffffffffffffffffffffffffffff16906020019092919080359060200190929190505050610e9e565b604051808215151515815260200191505060405180910390f35b610395611128565b604051808260ff1660ff16815260200191505060405180910390f35b6103b961112d565b6040518080602001828103825283818151815260200191508051906020019080838360005b838110156103f95780820151818401526020810190506103de565b50505050905090810190601f1680156104265780820380516001836020036101000a031916815260200191505b509250505060405180910390f35b6104806004803603604081101561044a57600080fd5b81019080803573ffffffffffffffffffffffffffffffffffffffff169060200190929190803590602001909291905050506111cb565b604051808215151515815260200191505060405180910390f35b6104a2611262565b005b6104e6600480360360208110156104ba57600080fd5b81019080803573ffffffffffffffffffffffffffffffffffffffff1690602001909291905050506113c2565b604051808215151515815260200191505060405180910390f35b6105086113df565b604051808215151515815260200191505060405180910390f35b6105846004803603604081101561053857600080fd5b81019080803573ffffffffffffffffffffffffffffffffffffffff169060200190929190803573ffffffffffffffffffffffffffffffffffffffff1690602001909291905050506113f6565b005b6105fd6004803603602081101561059c57600080fd5b81019080803590602001906401000000008111156105b957600080fd5b8201836020820111156105cb57600080fd5b803590602001918460018302840111640100000000831117156105ed57600080fd5b9091929391929390505050611984565b005b6106076119d7565b005b61064b6004803603602081101561061f57600080fd5b81019080803573ffffffffffffffffffffffffffffffffffffffff1690602001909291905050506119e2565b6040518082815260200191505060405180910390f35b610669611a2a565b005b61069a6004803603602081101561068157600080fd5b81019080803560ff169060200190929190505050611b96565b6040518080602001828103825283818151815260200191508051906020019080838360005b838110156106da5780820151818401526020810190506106bf565b50505050905090810190601f1680156107075780820380516001836020036101000a031916815260200191505b509250505060405180910390f35b61078c6004803603602081101561072b57600080fd5b810190808035906020019064010000000081111561074857600080fd5b82018360208201111561075a57600080fd5b8035906020019184600183028401116401000000008311171561077c57600080fd5b9091929391929390505050611e05565b005b6107d0600480360360208110156107a457600080fd5b81019080803573ffffffffffffffffffffffffffffffffffffffff169060200190929190505050611f41565b005b6107da611fab565b005b6107e461210c565b604051808273ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200191505060405180910390f35b61082e612132565b6040518080602001828103825283818151815260200191508051906020019080838360005b8381101561086e578082015181840152602081019050610853565b50505050905090810190601f16801561089b5780820380516001836020036101000a031916815260200191505b509250505060405180910390f35b6108f5600480360360408110156108bf57600080fd5b81019080803573ffffffffffffffffffffffffffffffffffffffff169060200190929190803590602001909291905050506121d0565b604051808215151515815260200191505060405180910390f35b6109516004803603602081101561092557600080fd5b81019080803573ffffffffffffffffffffffffffffffffffffffff169060200190929190505050612267565b005b61099f6004803603604081101561096957600080fd5b81019080803573ffffffffffffffffffffffffffffffffffffffff169060200190929190803590602001909291905050506123b1565b604051808215151515815260200191505060405180910390f35b610a30600480360360208110156109cf57600080fd5b81019080803590602001906401000000008111156109ec57600080fd5b8201836020820111156109fe57600080fd5b80359060200191846020830284011164010000000083111715610a2057600080fd5b9091929391929390505050612638565b005b610a5e60048036036020811015610a4857600080fd5b8101908080359060200190929190505050612ace565b005b610acc60048036036060811015610a7657600080fd5b81019080803573ffffffffffffffffffffffffffffffffffffffff169060200190929190803573ffffffffffffffffffffffffffffffffffffffff16906020019092919080359060200190929190505050612d45565b604051808260ff1660ff16815260200191505060405180910390f35b610b1460048036036020811015610afe57600080fd5b8101908080359060200190929190505050612edc565b005b610b7860048036036040811015610b2c57600080fd5b81019080803573ffffffffffffffffffffffffffffffffffffffff169060200190929190803573ffffffffffffffffffffffffffffffffffffffff169060200190929190505050613153565b6040518082815260200191505060405180910390f35b610bfa60048036036060811015610ba457600080fd5b81019080803573ffffffffffffffffffffffffffffffffffffffff169060200190929190803573ffffffffffffffffffffffffffffffffffffffff169060200190929190803590602001909291905050506131da565b604051808215151515815260200191505060405180910390f35b610c5660048036036020811015610c2a57600080fd5b81019080803573ffffffffffffffffffffffffffffffffffffffff169060200190929190505050613371565b6040518080602001828103825283818151815260200191508051906020019080838360005b83811015610c96578082015181840152602081019050610c7b565b50505050905090810190601f168015610cc35780820380516001836020036101000a031916815260200191505b509250505060405180910390f35b610d1360048036036020811015610ce757600080fd5b81019080803573ffffffffffffffffffffffffffffffffffffffff169060200190929190505050613452565b005b610d1d613521565b604051808273ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200191505060405180910390f35b60068054600181600116156101000203166002900480601f016020809104026020016040519081016040528092919081815260200182805460018160011615610100020316600290048015610df55780601f10610dca57610100808354040283529160200191610df5565b820191906000526020600020905b815481529060010190602001808311610dd857829003601f168201915b505050505081565b6000600560009054906101000a900460ff1615610e82576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260108152602001807f5061757361626c653a207061757365640000000000000000000000000000000081525060200191505060405180910390fd5b610e8c8383613547565b905092915050565b6000600254905090565b6000600560009054906101000a900460ff1615610f23576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260108152602001807f5061757361626c653a207061757365640000000000000000000000000000000081525060200191505060405180910390fd5b600073ffffffffffffffffffffffffffffffffffffffff16600a60009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff161461111357600a60009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1663c6946a128585856040518463ffffffff1660e01b8152600401808473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1681526020018373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff168152602001828152602001935050505060206040518083038186803b15801561105457600080fd5b505afa158015611068573d6000803e3d6000fd5b505050506040513d602081101561107e57600080fd5b8101908080519060200190929190505050611101576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260048152602001807f434d30340000000000000000000000000000000000000000000000000000000081525060200191505060405180910390fd5b61110c84848461355e565b9050611121565b61111e84848461355e565b90505b9392505050565b600081565b60088054600181600116156101000203166002900480601f0160208091040260200160405190810160405280929190818152602001828054600181600116156101000203166002900480156111c35780601f10611198576101008083540402835291602001916111c3565b820191906000526020600020905b8154815290600101906020018083116111a657829003601f168201915b505050505081565b6000600560009054906101000a900460ff1615611250576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260108152602001807f5061757361626c653a207061757365640000000000000000000000000000000081525060200191505060405180910390fd5b61125a838361360f565b905092915050565b61126b336113c2565b6112c0576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260308152602001806142ea6030913960400191505060405180910390fd5b600560009054906101000a900460ff16611342576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260148152602001807f5061757361626c653a206e6f742070617573656400000000000000000000000081525060200191505060405180910390fd5b6000600560006101000a81548160ff0219169083151502179055507f5db9ee0a495bf2e6ff9c91a7834c1ba4fdd244a5e8aa4e537bd38aeae4b073aa33604051808273ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200191505060405180910390a1565b60006113d88260046136b490919063ffffffff16565b9050919050565b6000600560009054906101000a900460ff16905090565b600360009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff163373ffffffffffffffffffffffffffffffffffffffff16146114b9576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260048152602001807f4f5730310000000000000000000000000000000000000000000000000000000081525060200191505060405180910390fd5b600560009054906101000a900460ff161561153c576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260108152602001807f5061757361626c653a207061757365640000000000000000000000000000000081525060200191505060405180910390fd5b600073ffffffffffffffffffffffffffffffffffffffff168273ffffffffffffffffffffffffffffffffffffffff1614156115df576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260048152602001807f434d30310000000000000000000000000000000000000000000000000000000081525060200191505060405180910390fd5b600073ffffffffffffffffffffffffffffffffffffffff168173ffffffffffffffffffffffffffffffffffffffff161415611682576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260048152602001807f434d30320000000000000000000000000000000000000000000000000000000081525060200191505060405180910390fd5b8073ffffffffffffffffffffffffffffffffffffffff168273ffffffffffffffffffffffffffffffffffffffff161415611724576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260048152602001807f434d30330000000000000000000000000000000000000000000000000000000081525060200191505060405180910390fd5b60008060008473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002054905060008114156117de576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260048152602001807f434d30350000000000000000000000000000000000000000000000000000000081525060200191505060405180910390fd5b61182f816000808573ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1681526020019081526020016000205461379290919063ffffffff16565b6000808473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1681526020019081526020016000208190555060008060008573ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff168152602001908152602001600020819055508173ffffffffffffffffffffffffffffffffffffffff168373ffffffffffffffffffffffffffffffffffffffff167fddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef836040518082815260200191505060405180910390a38173ffffffffffffffffffffffffffffffffffffffff168373ffffffffffffffffffffffffffffffffffffffff167f9b50bb42c2f723a111ed2b4a02d7963b78fcef409123755e32db36acf004c721836040518082815260200191505060405180910390a3505050565b8181600960003373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002091906119d29291906141a1565b505050565b6119e03361381a565b565b60008060008373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff168152602001908152602001600020549050919050565b600360009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff163373ffffffffffffffffffffffffffffffffffffffff1614611aed576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260048152602001807f4f5730310000000000000000000000000000000000000000000000000000000081525060200191505060405180910390fd5b600360009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff167ff8df31144d9c2f0f6b59d69b8b98abd5459d07f2742c4df920b25aae33c6482060405160405180910390a26000600360006101000a81548173ffffffffffffffffffffffffffffffffffffffff021916908373ffffffffffffffffffffffffffffffffffffffff160217905550565b6060600060ff168260ff161415611be4576040518060400160405280600e81526020017f4e6f207265737472696374696f6e0000000000000000000000000000000000008152509050611e00565b600160ff168260ff161415611c30576040518060400160405280601481526020017f416c6c207472616e7366657273207061757365640000000000000000000000008152509050611e00565b600073ffffffffffffffffffffffffffffffffffffffff16600a60009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1614611dff57600a60009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16637f4ab1dd836040518263ffffffff1660e01b8152600401808260ff1660ff16815260200191505060006040518083038186803b158015611cff57600080fd5b505afa158015611d13573d6000803e3d6000fd5b505050506040513d6000823e3d601f19601f820116820180604052506020811015611d3d57600080fd5b8101908080516040519392919084640100000000821115611d5d57600080fd5b83820191506020820185811115611d7357600080fd5b8251866001820283011164010000000082111715611d9057600080fd5b8083526020830192505050908051906020019080838360005b83811015611dc4578082015181840152602081019050611da9565b50505050905090810190601f168015611df15780820380516001836020036101000a031916815260200191505b506040525050509050611e00565b5b919050565b600360009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff163373ffffffffffffffffffffffffffffffffffffffff1614611ec8576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260048152602001807f4f5730310000000000000000000000000000000000000000000000000000000081525060200191505060405180910390fd5b818160089190611ed9929190614221565b507f188bad42ea723dd12513086ade62bd9d922818bd71ec4761f9b66c171c17dd0d828260405180806020018281038252848482818152602001925080828437600081840152601f19601f820116905080830192505050935050505060405180910390a15050565b611f4a336113c2565b611f9f576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260308152602001806142ea6030913960400191505060405180910390fd5b611fa881613874565b50565b611fb4336113c2565b612009576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260308152602001806142ea6030913960400191505060405180910390fd5b600560009054906101000a900460ff161561208c576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260108152602001807f5061757361626c653a207061757365640000000000000000000000000000000081525060200191505060405180910390fd5b6001600560006101000a81548160ff0219169083151502179055507f62e78cea01bee320cd4e420270b5ea74000d11b0c9f74754ebdbfc544b05a25833604051808273ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200191505060405180910390a1565b600360009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1681565b60078054600181600116156101000203166002900480601f0160208091040260200160405190810160405280929190818152602001828054600181600116156101000203166002900480156121c85780601f1061219d576101008083540402835291602001916121c8565b820191906000526020600020905b8154815290600101906020018083116121ab57829003601f168201915b505050505081565b6000600560009054906101000a900460ff1615612255576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260108152602001807f5061757361626c653a207061757365640000000000000000000000000000000081525060200191505060405180910390fd5b61225f83836138ce565b905092915050565b600360009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff163373ffffffffffffffffffffffffffffffffffffffff161461232a576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260048152602001807f4f5730310000000000000000000000000000000000000000000000000000000081525060200191505060405180910390fd5b80600a60006101000a81548173ffffffffffffffffffffffffffffffffffffffff021916908373ffffffffffffffffffffffffffffffffffffffff1602179055508073ffffffffffffffffffffffffffffffffffffffff167fc821fee57f621fad293a6960b94de2653a70bcc62506ea4f85149777b45901fe60405160405180910390a250565b6000600560009054906101000a900460ff1615612436576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260108152602001807f5061757361626c653a207061757365640000000000000000000000000000000081525060200191505060405180910390fd5b600073ffffffffffffffffffffffffffffffffffffffff16600a60009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff161461262557600a60009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1663c6946a123385856040518463ffffffff1660e01b8152600401808473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1681526020018373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff168152602001828152602001935050505060206040518083038186803b15801561256757600080fd5b505afa15801561257b573d6000803e3d6000fd5b505050506040513d602081101561259157600080fd5b8101908080519060200190929190505050612614576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260048152602001807f434d30340000000000000000000000000000000000000000000000000000000081525060200191505060405180910390fd5b61261e8383613973565b9050612632565b61262f8383613973565b90505b92915050565b600360009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff163373ffffffffffffffffffffffffffffffffffffffff16146126fb576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260048152602001807f4f5730310000000000000000000000000000000000000000000000000000000081525060200191505060405180910390fd5b60008090505b82829050811015612a6357600360009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1683838381811061275157fe5b9050602002013573ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1614156127f8576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260048152602001807f434d30360000000000000000000000000000000000000000000000000000000081525060200191505060405180910390fd5b600080600085858581811061280957fe5b9050602002013573ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1681526020019081526020016000205490506128d681600080600360009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1681526020019081526020016000205461379290919063ffffffff16565b600080600360009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002081905550600080600086868681811061294b57fe5b9050602002013573ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002081905550600360009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff168484848181106129eb57fe5b9050602002013573ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff167fddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef836040518082815260200191505060405180910390a3508080600101915050612701565b507fef8a7d1d9ed56b75ba2d074c0443d09a07e60674f3f6d4e992e9bda38efe5880828260405180806020018281038252848482818152602001925060200280828437600081840152601f19601f820116905080830192505050935050505060405180910390a15050565b600360009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff163373ffffffffffffffffffffffffffffffffffffffff1614612b91576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260048152602001807f4f5730310000000000000000000000000000000000000000000000000000000081525060200191505060405180910390fd5b612c0481600080600360009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1681526020019081526020016000205461379290919063ffffffff16565b600080600360009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002081905550612c7d8160025461379290919063ffffffff16565b600281905550600360009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16600073ffffffffffffffffffffffffffffffffffffffff167fddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef836040518082815260200191505060405180910390a37f5aa5d4dbb3bdc35fe42446ba12fc59cdd56ee008d5a8159ba5e5fb5834734f62816040518082815260200191505060405180910390a150565b6000612d4f6113df565b15612d5d5760019050612ed5565b600073ffffffffffffffffffffffffffffffffffffffff16600a60009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1614612ed057600a60009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1663d4ce14158585856040518463ffffffff1660e01b8152600401808473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1681526020018373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff168152602001828152602001935050505060206040518083038186803b158015612e8e57600080fd5b505afa158015612ea2573d6000803e3d6000fd5b505050506040513d6020811015612eb857600080fd5b81019080805190602001909291905050509050612ed5565b600090505b9392505050565b600360009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff163373ffffffffffffffffffffffffffffffffffffffff1614612f9f576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260048152602001807f4f5730310000000000000000000000000000000000000000000000000000000081525060200191505060405180910390fd5b61301281600080600360009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1681526020019081526020016000205461398a90919063ffffffff16565b600080600360009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1681526020019081526020016000208190555061308b8160025461398a90919063ffffffff16565b600281905550600073ffffffffffffffffffffffffffffffffffffffff16600360009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff167fddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef836040518082815260200191505060405180910390a37fe3dd692f7e5c129a26d85142bf6118f2ecf7722a79a4507ac05ad7bb7aaab152816040518082815260200191505060405180910390a150565b6000600160008473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060008373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002054905092915050565b60006131e46113df565b156131f2576000905061336a565b600073ffffffffffffffffffffffffffffffffffffffff16600a60009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff161461336557600a60009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1663c6946a128585856040518463ffffffff1660e01b8152600401808473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1681526020018373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff168152602001828152602001935050505060206040518083038186803b15801561332357600080fd5b505afa158015613337573d6000803e3d6000fd5b505050506040513d602081101561334d57600080fd5b8101908080519060200190929190505050905061336a565b600190505b9392505050565b6060600960008373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1681526020019081526020016000208054600181600116156101000203166002900480601f0160208091040260200160405190810160405280929190818152602001828054600181600116156101000203166002900480156134465780601f1061341b57610100808354040283529160200191613446565b820191906000526020600020905b81548152906001019060200180831161342957829003601f168201915b50505050509050919050565b600360009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff163373ffffffffffffffffffffffffffffffffffffffff1614613515576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260048152602001807f4f5730310000000000000000000000000000000000000000000000000000000081525060200191505060405180910390fd5b61351e81613a13565b50565b600a60009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1681565b6000613554338484613b76565b6001905092915050565b600061356b848484613d6d565b61360484336135ff85600160008a73ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060003373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1681526020019081526020016000205461398a90919063ffffffff16565b613b76565b600190509392505050565b60006136aa33846136a585600160003373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060008973ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1681526020019081526020016000205461379290919063ffffffff16565b613b76565b6001905092915050565b60008073ffffffffffffffffffffffffffffffffffffffff168273ffffffffffffffffffffffffffffffffffffffff16141561373b576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040180806020018281038252602281526020018061435d6022913960400191505060405180910390fd5b8260000160008373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060009054906101000a900460ff16905092915050565b600080828401905083811015613810576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040180806020018281038252601b8152602001807f536166654d6174683a206164646974696f6e206f766572666c6f77000000000081525060200191505060405180910390fd5b8091505092915050565b61382e81600461400990919063ffffffff16565b8073ffffffffffffffffffffffffffffffffffffffff167fcd265ebaf09df2871cc7bd4133404a235ba12eff2041bb89d9c714a2621c7c7e60405160405180910390a250565b6138888160046140c690919063ffffffff16565b8073ffffffffffffffffffffffffffffffffffffffff167f6719d08c1888103bea251a4ed56406bd0c3e69723c8a1686e017e7bbe159b6f860405160405180910390a250565b6000613969338461396485600160003373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060008973ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1681526020019081526020016000205461398a90919063ffffffff16565b613b76565b6001905092915050565b6000613980338484613d6d565b6001905092915050565b600082821115613a02576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040180806020018281038252601e8152602001807f536166654d6174683a207375627472616374696f6e206f766572666c6f77000081525060200191505060405180910390fd5b600082840390508091505092915050565b600073ffffffffffffffffffffffffffffffffffffffff168173ffffffffffffffffffffffffffffffffffffffff161415613ab6576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260048152602001807f4f5730320000000000000000000000000000000000000000000000000000000081525060200191505060405180910390fd5b8073ffffffffffffffffffffffffffffffffffffffff16600360009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff167f8be0079c531659141344cd1fd0a4f28419497f9722a3daafe3b4186f6b6457e060405160405180910390a380600360006101000a81548173ffffffffffffffffffffffffffffffffffffffff021916908373ffffffffffffffffffffffffffffffffffffffff16021790555050565b600073ffffffffffffffffffffffffffffffffffffffff168373ffffffffffffffffffffffffffffffffffffffff161415613bfc576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260248152602001806143a46024913960400191505060405180910390fd5b600073ffffffffffffffffffffffffffffffffffffffff168273ffffffffffffffffffffffffffffffffffffffff161415613c82576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040180806020018281038252602281526020018061431a6022913960400191505060405180910390fd5b80600160008573ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060008473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff168152602001908152602001600020819055508173ffffffffffffffffffffffffffffffffffffffff168373ffffffffffffffffffffffffffffffffffffffff167f8c5be1e5ebec7d5bd14f71427d1e84f3dd0314c0f7b2291e5b200ac8c7c3b925836040518082815260200191505060405180910390a3505050565b600073ffffffffffffffffffffffffffffffffffffffff168373ffffffffffffffffffffffffffffffffffffffff161415613df3576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040180806020018281038252602581526020018061437f6025913960400191505060405180910390fd5b600073ffffffffffffffffffffffffffffffffffffffff168273ffffffffffffffffffffffffffffffffffffffff161415613e79576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260238152602001806142c76023913960400191505060405180910390fd5b613eca816000808673ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1681526020019081526020016000205461398a90919063ffffffff16565b6000808573ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002081905550613f5d816000808573ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1681526020019081526020016000205461379290919063ffffffff16565b6000808473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff168152602001908152602001600020819055508173ffffffffffffffffffffffffffffffffffffffff168373ffffffffffffffffffffffffffffffffffffffff167fddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef836040518082815260200191505060405180910390a3505050565b61401382826136b4565b614068576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040180806020018281038252602181526020018061433c6021913960400191505060405180910390fd5b60008260000160008373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060006101000a81548160ff0219169083151502179055505050565b6140d082826136b4565b15614143576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040180806020018281038252601f8152602001807f526f6c65733a206163636f756e7420616c72656164792068617320726f6c650081525060200191505060405180910390fd5b60018260000160008373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060006101000a81548160ff0219169083151502179055505050565b828054600181600116156101000203166002900490600052602060002090601f016020900481019282601f106141e257803560ff1916838001178555614210565b82800160010185558215614210579182015b8281111561420f5782358255916020019190600101906141f4565b5b50905061421d91906142a1565b5090565b828054600181600116156101000203166002900490600052602060002090601f016020900481019282601f1061426257803560ff1916838001178555614290565b82800160010185558215614290579182015b8281111561428f578235825591602001919060010190614274565b5b50905061429d91906142a1565b5090565b6142c391905b808211156142bf5760008160009055506001016142a7565b5090565b9056fe45524332303a207472616e7366657220746f20746865207a65726f2061646472657373506175736572526f6c653a2063616c6c657220646f6573206e6f742068617665207468652050617573657220726f6c6545524332303a20617070726f766520746f20746865207a65726f2061646472657373526f6c65733a206163636f756e7420646f6573206e6f74206861766520726f6c65526f6c65733a206163636f756e7420697320746865207a65726f206164647265737345524332303a207472616e736665722066726f6d20746865207a65726f206164647265737345524332303a20617070726f76652066726f6d20746865207a65726f2061646472657373a265627a7a72315820c480f6e7b90434b4759339b017f6f12bfad33b496cab38cbc38245a47759fb2d64736f6c63430005110032526f6c65733a206163636f756e7420697320746865207a65726f2061646472657373"
         self.abi = [
                    	{
                    		"inputs": [
                    			{
                    				"internalType": "string",
                    				"name": "_name",
                    				"type": "string"
                    			},
                    			{
                    				"internalType": "string",
                    				"name": "_symbol",
                    				"type": "string"
                    			},
                    			{
                    				"internalType": "string",
                    				"name": "_contact",
                    				"type": "string"
                    			}
                    		],
                    		"payable": False,
                    		"stateMutability": "nonpayable",
                    		"type": "constructor"
                    	},
                    	{
                    		"anonymous": False,
                    		"inputs": [
                    			{
                    				"indexed": True,
                    				"internalType": "address",
                    				"name": "owner",
                    				"type": "address"
                    			},
                    			{
                    				"indexed": True,
                    				"internalType": "address",
                    				"name": "spender",
                    				"type": "address"
                    			},
                    			{
                    				"indexed": False,
                    				"internalType": "uint256",
                    				"name": "value",
                    				"type": "uint256"
                    			}
                    		],
                    		"name": "Approval",
                    		"type": "event"
                    	},
                    	{
                    		"anonymous": False,
                    		"inputs": [
                    			{
                    				"indexed": False,
                    				"internalType": "string",
                    				"name": "contact",
                    				"type": "string"
                    			}
                    		],
                    		"name": "LogContactSet",
                    		"type": "event"
                    	},
                    	{
                    		"anonymous": False,
                    		"inputs": [
                    			{
                    				"indexed": False,
                    				"internalType": "address[]",
                    				"name": "shareholders",
                    				"type": "address[]"
                    			}
                    		],
                    		"name": "LogDestroyed",
                    		"type": "event"
                    	},
                    	{
                    		"anonymous": False,
                    		"inputs": [
                    			{
                    				"indexed": False,
                    				"internalType": "uint256",
                    				"name": "value",
                    				"type": "uint256"
                    			}
                    		],
                    		"name": "LogIssued",
                    		"type": "event"
                    	},
                    	{
                    		"anonymous": False,
                    		"inputs": [
                    			{
                    				"indexed": True,
                    				"internalType": "address",
                    				"name": "original",
                    				"type": "address"
                    			},
                    			{
                    				"indexed": True,
                    				"internalType": "address",
                    				"name": "replacement",
                    				"type": "address"
                    			},
                    			{
                    				"indexed": False,
                    				"internalType": "uint256",
                    				"name": "value",
                    				"type": "uint256"
                    			}
                    		],
                    		"name": "LogReassigned",
                    		"type": "event"
                    	},
                    	{
                    		"anonymous": False,
                    		"inputs": [
                    			{
                    				"indexed": False,
                    				"internalType": "uint256",
                    				"name": "value",
                    				"type": "uint256"
                    			}
                    		],
                    		"name": "LogRedeemed",
                    		"type": "event"
                    	},
                    	{
                    		"anonymous": False,
                    		"inputs": [
                    			{
                    				"indexed": True,
                    				"internalType": "address",
                    				"name": "newRuleEngine",
                    				"type": "address"
                    			}
                    		],
                    		"name": "LogRuleEngineSet",
                    		"type": "event"
                    	},
                    	{
                    		"anonymous": False,
                    		"inputs": [
                    			{
                    				"indexed": True,
                    				"internalType": "address",
                    				"name": "previousOwner",
                    				"type": "address"
                    			}
                    		],
                    		"name": "OwnershipRenounced",
                    		"type": "event"
                    	},
                    	{
                    		"anonymous": False,
                    		"inputs": [
                    			{
                    				"indexed": True,
                    				"internalType": "address",
                    				"name": "previousOwner",
                    				"type": "address"
                    			},
                    			{
                    				"indexed": True,
                    				"internalType": "address",
                    				"name": "newOwner",
                    				"type": "address"
                    			}
                    		],
                    		"name": "OwnershipTransferred",
                    		"type": "event"
                    	},
                    	{
                    		"anonymous": False,
                    		"inputs": [
                    			{
                    				"indexed": False,
                    				"internalType": "address",
                    				"name": "account",
                    				"type": "address"
                    			}
                    		],
                    		"name": "Paused",
                    		"type": "event"
                    	},
                    	{
                    		"anonymous": False,
                    		"inputs": [
                    			{
                    				"indexed": True,
                    				"internalType": "address",
                    				"name": "account",
                    				"type": "address"
                    			}
                    		],
                    		"name": "PauserAdded",
                    		"type": "event"
                    	},
                    	{
                    		"anonymous": False,
                    		"inputs": [
                    			{
                    				"indexed": True,
                    				"internalType": "address",
                    				"name": "account",
                    				"type": "address"
                    			}
                    		],
                    		"name": "PauserRemoved",
                    		"type": "event"
                    	},
                    	{
                    		"anonymous": False,
                    		"inputs": [
                    			{
                    				"indexed": True,
                    				"internalType": "address",
                    				"name": "from",
                    				"type": "address"
                    			},
                    			{
                    				"indexed": True,
                    				"internalType": "address",
                    				"name": "to",
                    				"type": "address"
                    			},
                    			{
                    				"indexed": False,
                    				"internalType": "uint256",
                    				"name": "value",
                    				"type": "uint256"
                    			}
                    		],
                    		"name": "Transfer",
                    		"type": "event"
                    	},
                    	{
                    		"anonymous": False,
                    		"inputs": [
                    			{
                    				"indexed": False,
                    				"internalType": "address",
                    				"name": "account",
                    				"type": "address"
                    			}
                    		],
                    		"name": "Unpaused",
                    		"type": "event"
                    	},
                    	{
                    		"constant": False,
                    		"inputs": [
                    			{
                    				"internalType": "address",
                    				"name": "account",
                    				"type": "address"
                    			}
                    		],
                    		"name": "addPauser",
                    		"outputs": [],
                    		"payable": False,
                    		"stateMutability": "nonpayable",
                    		"type": "function"
                    	},
                    	{
                    		"constant": True,
                    		"inputs": [
                    			{
                    				"internalType": "address",
                    				"name": "owner",
                    				"type": "address"
                    			},
                    			{
                    				"internalType": "address",
                    				"name": "spender",
                    				"type": "address"
                    			}
                    		],
                    		"name": "allowance",
                    		"outputs": [
                    			{
                    				"internalType": "uint256",
                    				"name": "",
                    				"type": "uint256"
                    			}
                    		],
                    		"payable": False,
                    		"stateMutability": "view",
                    		"type": "function"
                    	},
                    	{
                    		"constant": False,
                    		"inputs": [
                    			{
                    				"internalType": "address",
                    				"name": "_spender",
                    				"type": "address"
                    			},
                    			{
                    				"internalType": "uint256",
                    				"name": "_value",
                    				"type": "uint256"
                    			}
                    		],
                    		"name": "approve",
                    		"outputs": [
                    			{
                    				"internalType": "bool",
                    				"name": "",
                    				"type": "bool"
                    			}
                    		],
                    		"payable": False,
                    		"stateMutability": "nonpayable",
                    		"type": "function"
                    	},
                    	{
                    		"constant": True,
                    		"inputs": [
                    			{
                    				"internalType": "address",
                    				"name": "account",
                    				"type": "address"
                    			}
                    		],
                    		"name": "balanceOf",
                    		"outputs": [
                    			{
                    				"internalType": "uint256",
                    				"name": "",
                    				"type": "uint256"
                    			}
                    		],
                    		"payable": False,
                    		"stateMutability": "view",
                    		"type": "function"
                    	},
                    	{
                    		"constant": True,
                    		"inputs": [
                    			{
                    				"internalType": "address",
                    				"name": "_from",
                    				"type": "address"
                    			},
                    			{
                    				"internalType": "address",
                    				"name": "_to",
                    				"type": "address"
                    			},
                    			{
                    				"internalType": "uint256",
                    				"name": "_value",
                    				"type": "uint256"
                    			}
                    		],
                    		"name": "canTransfer",
                    		"outputs": [
                    			{
                    				"internalType": "bool",
                    				"name": "",
                    				"type": "bool"
                    			}
                    		],
                    		"payable": False,
                    		"stateMutability": "view",
                    		"type": "function"
                    	},
                    	{
                    		"constant": True,
                    		"inputs": [],
                    		"name": "contact",
                    		"outputs": [
                    			{
                    				"internalType": "string",
                    				"name": "",
                    				"type": "string"
                    			}
                    		],
                    		"payable": False,
                    		"stateMutability": "view",
                    		"type": "function"
                    	},
                    	{
                    		"constant": True,
                    		"inputs": [],
                    		"name": "decimals",
                    		"outputs": [
                    			{
                    				"internalType": "uint8",
                    				"name": "",
                    				"type": "uint8"
                    			}
                    		],
                    		"payable": False,
                    		"stateMutability": "view",
                    		"type": "function"
                    	},
                    	{
                    		"constant": False,
                    		"inputs": [
                    			{
                    				"internalType": "address",
                    				"name": "_spender",
                    				"type": "address"
                    			},
                    			{
                    				"internalType": "uint256",
                    				"name": "_subtractedValue",
                    				"type": "uint256"
                    			}
                    		],
                    		"name": "decreaseAllowance",
                    		"outputs": [
                    			{
                    				"internalType": "bool",
                    				"name": "",
                    				"type": "bool"
                    			}
                    		],
                    		"payable": False,
                    		"stateMutability": "nonpayable",
                    		"type": "function"
                    	},
                    	{
                    		"constant": False,
                    		"inputs": [
                    			{
                    				"internalType": "address[]",
                    				"name": "shareholders",
                    				"type": "address[]"
                    			}
                    		],
                    		"name": "destroy",
                    		"outputs": [],
                    		"payable": False,
                    		"stateMutability": "nonpayable",
                    		"type": "function"
                    	},
                    	{
                    		"constant": True,
                    		"inputs": [
                    			{
                    				"internalType": "address",
                    				"name": "_from",
                    				"type": "address"
                    			},
                    			{
                    				"internalType": "address",
                    				"name": "_to",
                    				"type": "address"
                    			},
                    			{
                    				"internalType": "uint256",
                    				"name": "_value",
                    				"type": "uint256"
                    			}
                    		],
                    		"name": "detectTransferRestriction",
                    		"outputs": [
                    			{
                    				"internalType": "uint8",
                    				"name": "",
                    				"type": "uint8"
                    			}
                    		],
                    		"payable": False,
                    		"stateMutability": "view",
                    		"type": "function"
                    	},
                    	{
                    		"constant": True,
                    		"inputs": [
                    			{
                    				"internalType": "address",
                    				"name": "shareholder",
                    				"type": "address"
                    			}
                    		],
                    		"name": "identity",
                    		"outputs": [
                    			{
                    				"internalType": "bytes",
                    				"name": "",
                    				"type": "bytes"
                    			}
                    		],
                    		"payable": False,
                    		"stateMutability": "view",
                    		"type": "function"
                    	},
                    	{
                    		"constant": False,
                    		"inputs": [
                    			{
                    				"internalType": "address",
                    				"name": "_spender",
                    				"type": "address"
                    			},
                    			{
                    				"internalType": "uint256",
                    				"name": "_addedValue",
                    				"type": "uint256"
                    			}
                    		],
                    		"name": "increaseAllowance",
                    		"outputs": [
                    			{
                    				"internalType": "bool",
                    				"name": "",
                    				"type": "bool"
                    			}
                    		],
                    		"payable": False,
                    		"stateMutability": "nonpayable",
                    		"type": "function"
                    	},
                    	{
                    		"constant": True,
                    		"inputs": [
                    			{
                    				"internalType": "address",
                    				"name": "account",
                    				"type": "address"
                    			}
                    		],
                    		"name": "isPauser",
                    		"outputs": [
                    			{
                    				"internalType": "bool",
                    				"name": "",
                    				"type": "bool"
                    			}
                    		],
                    		"payable": False,
                    		"stateMutability": "view",
                    		"type": "function"
                    	},
                    	{
                    		"constant": False,
                    		"inputs": [
                    			{
                    				"internalType": "uint256",
                    				"name": "_value",
                    				"type": "uint256"
                    			}
                    		],
                    		"name": "issue",
                    		"outputs": [],
                    		"payable": False,
                    		"stateMutability": "nonpayable",
                    		"type": "function"
                    	},
                    	{
                    		"constant": True,
                    		"inputs": [
                    			{
                    				"internalType": "uint8",
                    				"name": "_restrictionCode",
                    				"type": "uint8"
                    			}
                    		],
                    		"name": "messageForTransferRestriction",
                    		"outputs": [
                    			{
                    				"internalType": "string",
                    				"name": "",
                    				"type": "string"
                    			}
                    		],
                    		"payable": False,
                    		"stateMutability": "view",
                    		"type": "function"
                    	},
                    	{
                    		"constant": True,
                    		"inputs": [],
                    		"name": "name",
                    		"outputs": [
                    			{
                    				"internalType": "string",
                    				"name": "",
                    				"type": "string"
                    			}
                    		],
                    		"payable": False,
                    		"stateMutability": "view",
                    		"type": "function"
                    	},
                    	{
                    		"constant": True,
                    		"inputs": [],
                    		"name": "owner",
                    		"outputs": [
                    			{
                    				"internalType": "address",
                    				"name": "",
                    				"type": "address"
                    			}
                    		],
                    		"payable": False,
                    		"stateMutability": "view",
                    		"type": "function"
                    	},
                    	{
                    		"constant": False,
                    		"inputs": [],
                    		"name": "pause",
                    		"outputs": [],
                    		"payable": False,
                    		"stateMutability": "nonpayable",
                    		"type": "function"
                    	},
                    	{
                    		"constant": True,
                    		"inputs": [],
                    		"name": "paused",
                    		"outputs": [
                    			{
                    				"internalType": "bool",
                    				"name": "",
                    				"type": "bool"
                    			}
                    		],
                    		"payable": False,
                    		"stateMutability": "view",
                    		"type": "function"
                    	},
                    	{
                    		"constant": False,
                    		"inputs": [
                    			{
                    				"internalType": "address",
                    				"name": "original",
                    				"type": "address"
                    			},
                    			{
                    				"internalType": "address",
                    				"name": "replacement",
                    				"type": "address"
                    			}
                    		],
                    		"name": "reassign",
                    		"outputs": [],
                    		"payable": False,
                    		"stateMutability": "nonpayable",
                    		"type": "function"
                    	},
                    	{
                    		"constant": False,
                    		"inputs": [
                    			{
                    				"internalType": "uint256",
                    				"name": "_value",
                    				"type": "uint256"
                    			}
                    		],
                    		"name": "redeem",
                    		"outputs": [],
                    		"payable": False,
                    		"stateMutability": "nonpayable",
                    		"type": "function"
                    	},
                    	{
                    		"constant": False,
                    		"inputs": [],
                    		"name": "renounceOwnership",
                    		"outputs": [],
                    		"payable": False,
                    		"stateMutability": "nonpayable",
                    		"type": "function"
                    	},
                    	{
                    		"constant": False,
                    		"inputs": [],
                    		"name": "renouncePauser",
                    		"outputs": [],
                    		"payable": False,
                    		"stateMutability": "nonpayable",
                    		"type": "function"
                    	},
                    	{
                    		"constant": True,
                    		"inputs": [],
                    		"name": "ruleEngine",
                    		"outputs": [
                    			{
                    				"internalType": "contract IRuleEngine",
                    				"name": "",
                    				"type": "address"
                    			}
                    		],
                    		"payable": False,
                    		"stateMutability": "view",
                    		"type": "function"
                    	},
                    	{
                    		"constant": False,
                    		"inputs": [
                    			{
                    				"internalType": "string",
                    				"name": "_contact",
                    				"type": "string"
                    			}
                    		],
                    		"name": "setContact",
                    		"outputs": [],
                    		"payable": False,
                    		"stateMutability": "nonpayable",
                    		"type": "function"
                    	},
                    	{
                    		"constant": False,
                    		"inputs": [
                    			{
                    				"internalType": "bytes",
                    				"name": "_identity",
                    				"type": "bytes"
                    			}
                    		],
                    		"name": "setMyIdentity",
                    		"outputs": [],
                    		"payable": False,
                    		"stateMutability": "nonpayable",
                    		"type": "function"
                    	},
                    	{
                    		"constant": False,
                    		"inputs": [
                    			{
                    				"internalType": "contract IRuleEngine",
                    				"name": "_ruleEngine",
                    				"type": "address"
                    			}
                    		],
                    		"name": "setRuleEngine",
                    		"outputs": [],
                    		"payable": False,
                    		"stateMutability": "nonpayable",
                    		"type": "function"
                    	},
                    	{
                    		"constant": True,
                    		"inputs": [],
                    		"name": "symbol",
                    		"outputs": [
                    			{
                    				"internalType": "string",
                    				"name": "",
                    				"type": "string"
                    			}
                    		],
                    		"payable": False,
                    		"stateMutability": "view",
                    		"type": "function"
                    	},
                    	{
                    		"constant": True,
                    		"inputs": [],
                    		"name": "totalSupply",
                    		"outputs": [
                    			{
                    				"internalType": "uint256",
                    				"name": "",
                    				"type": "uint256"
                    			}
                    		],
                    		"payable": False,
                    		"stateMutability": "view",
                    		"type": "function"
                    	},
                    	{
                    		"constant": False,
                    		"inputs": [
                    			{
                    				"internalType": "address",
                    				"name": "_to",
                    				"type": "address"
                    			},
                    			{
                    				"internalType": "uint256",
                    				"name": "_value",
                    				"type": "uint256"
                    			}
                    		],
                    		"name": "transfer",
                    		"outputs": [
                    			{
                    				"internalType": "bool",
                    				"name": "",
                    				"type": "bool"
                    			}
                    		],
                    		"payable": False,
                    		"stateMutability": "nonpayable",
                    		"type": "function"
                    	},
                    	{
                    		"constant": False,
                    		"inputs": [
                    			{
                    				"internalType": "address",
                    				"name": "_from",
                    				"type": "address"
                    			},
                    			{
                    				"internalType": "address",
                    				"name": "_to",
                    				"type": "address"
                    			},
                    			{
                    				"internalType": "uint256",
                    				"name": "_value",
                    				"type": "uint256"
                    			}
                    		],
                    		"name": "transferFrom",
                    		"outputs": [
                    			{
                    				"internalType": "bool",
                    				"name": "",
                    				"type": "bool"
                    			}
                    		],
                    		"payable": False,
                    		"stateMutability": "nonpayable",
                    		"type": "function"
                    	},
                    	{
                    		"constant": False,
                    		"inputs": [
                    			{
                    				"internalType": "address",
                    				"name": "_newOwner",
                    				"type": "address"
                    			}
                    		],
                    		"name": "transferOwnership",
                    		"outputs": [],
                    		"payable": False,
                    		"stateMutability": "nonpayable",
                    		"type": "function"
                    	},
                    	{
                    		"constant": False,
                    		"inputs": [],
                    		"name": "unpause",
                    		"outputs": [],
                    		"payable": False,
                    		"stateMutability": "nonpayable",
                    		"type": "function"
                    	}
                    ]

if __name__ == '__main__':
   erc = Erc721("", "ether", "testnet")
   erc.connect()
