from web3 import Web3
from web3 import exceptions
from web3.middleware import geth_poa_middleware
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
                "mainnet": "https://polygon-rpc.com",
                "testnet": "https://rpc-mumbai.matic.today"
            },
            "ether": {
                "testnet": "https://ropsten.infura.io/v3/9aa3d95b3bc440fa88ea12eaa4456161"
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
        provider = self.networks[self.network_type][self.network]
        self.link = Web3(Web3.HTTPProvider(provider))
        self.link.middleware_onion.inject(geth_poa_middleware, layer=0)
        self.link.eth.account.enable_unaudited_hdwallet_features()
        self.unit = 'ETH' if self.network_type == 'ether' else 'MATIC' if self.network_type == 'polygon' else ''
        return [True, f"Connected to {provider}", None]

    def execute_transaction(self, transaction, owner_address, owner_key, additionnal_gas = 0):
        gas_cost = transaction.estimateGas({'from': owner_address})
        gas_cost = gas_cost + additionnal_gas
        gas_price = self.link.toWei(150, 'gwei')
        ether_cost = float(self.link.fromWei(gas_price * gas_cost, 'ether'))
        success = False
        while success is False:
            try:
                build = transaction.buildTransaction({
                  'from': owner_address,
                  'gas': gas_cost,
                  'gasPrice': gas_price,
                  'nonce': self.link.eth.getTransactionCount(owner_address, "pending")
                })
                success = True
            except requests.exceptions.HTTPError:
                pass
        signed_txn = self.link.eth.account.signTransaction(build, private_key=owner_key)
        txn = self.link.eth.sendRawTransaction(signed_txn.rawTransaction).hex()
        txn_receipt = dict(self.link.eth.waitForTransactionReceipt(txn))
        del txn_receipt['logs']
        del txn_receipt['logsBloom']
        txn_receipt = self.hextojson(txn_receipt)
        return [True, {"transact": txn, "cost": ether_cost, 'unit': self.unit, 'return': txn_receipt}, None]

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
            self.red = get_conn().db("wallet").table('contracts
            self.trx = get_conn().db("wallet").table('transactions')
        except:
            self.red = None
            self.trx = None

    def get_contract(self):
        return self.link.eth.contract(self.address, abi=self.abi)

    def get_functions(self, id):
        contract = dict(self.red.get(id).run())
        functions = contract["deployment_infos"]["functions"]
        return [True, functions, None]

    def get_transaction(self, id):
        contract = dict(self.red.get(id).run())
        address = contract["address"]
        transactions = list(self.trx.get(
                (r.row["address"] ==  address)
                & (r.row["type"] ==  'contract')
            ).run())
        return [True, transactions, None]

    def exec_function(self, name, kwargs):
        keep_function = None
        for function in self.abi:
            if 'type' in function and function['type'] == 'function':
                if 'name' in function and function['name'] == name:
                    keep_function = function
        if keep_function is None:
            return [False, "Invalid function name", 400]
        for elem in keep_function['inputs']:
            elem_name = elem['name']
            elem_type = elem['type']
            if elem_name not in kwargs:
                return [False, f"missing {elem_name}:{elem_type}", 400]
        contract = self.link.eth.contract(self.address, abi=self.abi)
        transaction = contract.get_function_by_name(name)(**kwargs)
        if keep_function['stateMutability'] == 'view':
            return [True, self.hextojson({'result': transaction.call()}), None]
        owner = self.owner()
        return self.execute_transaction(transaction, owner.address, owner.key)

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

    def deploy(self, kwargs):
        owner = self.owner()
        constructor = [i for i in self.abi if 'type' in i and i['type'] == 'constructor']
        if len(constructor) == 0:
            return [False, "can't deploy that contract", 400]
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
        ret = self.execute_transaction(transaction, owner.address, owner.key, additionnal_gas = 300000)
        if not ret[0]:
            return ret
        data = {
            'deployment_infos': {
                "log": ret[1],
                "abi": self.abi,
                "bytecode": self.bytecode,
                "functions": self.__get_simplified('function'),
                "constructor": self.__get_simplified('constructor')
            },
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
         self.bytecode = "0x60806040523480156200001157600080fd5b506040516200424b3803806200424b833981810160405260608110156200003757600080fd5b81019080805160405193929190846401000000008211156200005857600080fd5b838201915060208201858111156200006f57600080fd5b82518660018202830111640100000000821117156200008d57600080fd5b8083526020830192505050908051906020019080838360005b83811015620000c3578082015181840152602081019050620000a6565b50505050905090810190601f168015620000f15780820380516001836020036101000a031916815260200191505b50604052602001805160405193929190846401000000008211156200011557600080fd5b838201915060208201858111156200012c57600080fd5b82518660018202830111640100000000821117156200014a57600080fd5b8083526020830192505050908051906020019080838360005b838110156200018057808201518184015260208101905062000163565b50505050905090810190601f168015620001ae5780820380516001836020036101000a031916815260200191505b5060405260200180516040519392919084640100000000821115620001d257600080fd5b83820191506020820185811115620001e957600080fd5b82518660018202830111640100000000821117156200020757600080fd5b8083526020830192505050908051906020019080838360005b838110156200023d57808201518184015260208101905062000220565b50505050905090810190601f1680156200026b5780820380516001836020036101000a031916815260200191505b5060405250505082826200028c6301ffc9a760e01b620003e360201b60201c565b8160079080519060200190620002a49291906200069e565b508060089080519060200190620002bd9291906200069e565b50620002d66380ac58cd60e01b620003e360201b60201c565b620002ee635b5e139f60e01b620003e360201b60201c565b6200030663780e9d6360e01b620003e360201b60201c565b50506000600b60006101000a81548160ff021916908315150217905550620003476000801b6200033b620004ec60201b60201c565b620004f460201b60201c565b620003887f9f2df0fed2c77648de5860a4cc508cd0818c85b8b8a1ab4ceeef8d981c8956a66200037c620004ec60201b60201c565b620004f460201b60201c565b620003c97f65d7a28e3265b37a6474929f336521b332c1681b933f6cb9f3376673440d862a620003bd620004ec60201b60201c565b620004f460201b60201c565b620003da816200050a60201b60201c565b50505062000744565b63ffffffff60e01b817bffffffffffffffffffffffffffffffffffffffffffffffffffffffff1916141562000480576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040180806020018281038252601c8152602001807f4552433136353a20696e76616c696420696e746572666163652069640000000081525060200191505060405180910390fd5b6001806000837bffffffffffffffffffffffffffffffffffffffffffffffffffffffff19167bffffffffffffffffffffffffffffffffffffffffffffffffffffffff1916815260200190815260200160002060006101000a81548160ff02191690831515021790555050565b600033905090565b6200050682826200052660201b60201c565b5050565b80600a9080519060200190620005229291906200069e565b5050565b6200055481600080858152602001908152602001600020600001620005c960201b62001d601790919060201c565b15620005c5576200056a620004ec60201b60201c565b73ffffffffffffffffffffffffffffffffffffffff168173ffffffffffffffffffffffffffffffffffffffff16837f2f8788117e7eff1d82e926ec794901d17c78024a50270940304540a733656f0d60405160405180910390a45b5050565b6000620005f9836000018373ffffffffffffffffffffffffffffffffffffffff1660001b6200060160201b60201c565b905092915050565b60006200061583836200067b60201b60201c565b6200067057826000018290806001815401808255809150506001900390600052602060002001600090919091909150558260000180549050836001016000848152602001908152602001600020819055506001905062000675565b600090505b92915050565b600080836001016000848152602001908152602001600020541415905092915050565b828054600181600116156101000203166002900490600052602060002090601f016020900481019282601f10620006e157805160ff191683800117855562000712565b8280016001018555821562000712579182015b8281111562000711578251825591602001919060010190620006f4565b5b50905062000721919062000725565b5090565b5b808211156200074057600081600090555060010162000726565b5090565b613af780620007546000396000f3fe608060405234801561001057600080fd5b50600436106101f05760003560e01c80636a6278421161010f578063a22cb465116100a2578063d539139311610071578063d539139314610b7b578063d547741f14610b99578063e63ab1e914610be7578063e985e9c514610c05576101f0565b8063a22cb4651461093d578063b88d4fde1461098d578063c87b56dd14610a92578063ca15c87314610b39576101f0565b80639010d07c116100de5780639010d07c146107d657806391d148541461083857806395d89b411461089c578063a217fddf1461091f576101f0565b80636a627842146106ad5780636c0360eb146106f157806370a08231146107745780638456cb59146107cc576101f0565b80632f745c591161018757806342966c681161015657806342966c68146105c55780634f6ccce7146105f35780635c975abb146106355780636352211e14610655576101f0565b80632f745c591461049d57806336568abe146104ff5780633f4ba83a1461054d57806342842e0e14610557576101f0565b806318160ddd116101c357806318160ddd1461038157806323b872dd1461039f578063248a9ca31461040d5780632f2ff15d1461044f576101f0565b806301ffc9a7146101f557806306fdde0314610258578063081812fc146102db578063095ea7b314610333575b600080fd5b6102406004803603602081101561020b57600080fd5b8101908080357bffffffffffffffffffffffffffffffffffffffffffffffffffffffff19169060200190929190505050610c7f565b60405180821515815260200191505060405180910390f35b610260610ce7565b6040518080602001828103825283818151815260200191508051906020019080838360005b838110156102a0578082015181840152602081019050610285565b50505050905090810190601f1680156102cd5780820380516001836020036101000a031916815260200191505b509250505060405180910390f35b610307600480360360208110156102f157600080fd5b8101908080359060200190929190505050610d89565b604051808273ffffffffffffffffffffffffffffffffffffffff16815260200191505060405180910390f35b61037f6004803603604081101561034957600080fd5b81019080803573ffffffffffffffffffffffffffffffffffffffff16906020019092919080359060200190929190505050610e24565b005b610389610f68565b6040518082815260200191505060405180910390f35b61040b600480360360608110156103b557600080fd5b81019080803573ffffffffffffffffffffffffffffffffffffffff169060200190929190803573ffffffffffffffffffffffffffffffffffffffff16906020019092919080359060200190929190505050610f79565b005b6104396004803603602081101561042357600080fd5b8101908080359060200190929190505050610fef565b6040518082815260200191505060405180910390f35b61049b6004803603604081101561046557600080fd5b8101908080359060200190929190803573ffffffffffffffffffffffffffffffffffffffff16906020019092919050505061100e565b005b6104e9600480360360408110156104b357600080fd5b81019080803573ffffffffffffffffffffffffffffffffffffffff16906020019092919080359060200190929190505050611097565b6040518082815260200191505060405180910390f35b61054b6004803603604081101561051557600080fd5b8101908080359060200190929190803573ffffffffffffffffffffffffffffffffffffffff1690602001909291905050506110f2565b005b61055561118b565b005b6105c36004803603606081101561056d57600080fd5b81019080803573ffffffffffffffffffffffffffffffffffffffff169060200190929190803573ffffffffffffffffffffffffffffffffffffffff1690602001909291908035906020019092919050505061121b565b005b6105f1600480360360208110156105db57600080fd5b810190808035906020019092919050505061123b565b005b61061f6004803603602081101561060957600080fd5b81019080803590602001909291905050506112ad565b6040518082815260200191505060405180910390f35b61063d6112d0565b60405180821515815260200191505060405180910390f35b6106816004803603602081101561066b57600080fd5b81019080803590602001909291905050506112e7565b604051808273ffffffffffffffffffffffffffffffffffffffff16815260200191505060405180910390f35b6106ef600480360360208110156106c357600080fd5b81019080803573ffffffffffffffffffffffffffffffffffffffff16906020019092919050505061131e565b005b6106f96113c4565b6040518080602001828103825283818151815260200191508051906020019080838360005b8381101561073957808201518184015260208101905061071e565b50505050905090810190601f1680156107665780820380516001836020036101000a031916815260200191505b509250505060405180910390f35b6107b66004803603602081101561078a57600080fd5b81019080803573ffffffffffffffffffffffffffffffffffffffff169060200190929190505050611466565b6040518082815260200191505060405180910390f35b6107d461153b565b005b61080c600480360360408110156107ec57600080fd5b8101908080359060200190929190803590602001909291905050506115cb565b604051808273ffffffffffffffffffffffffffffffffffffffff16815260200191505060405180910390f35b6108846004803603604081101561084e57600080fd5b8101908080359060200190929190803573ffffffffffffffffffffffffffffffffffffffff1690602001909291905050506115fc565b60405180821515815260200191505060405180910390f35b6108a461162d565b6040518080602001828103825283818151815260200191508051906020019080838360005b838110156108e45780820151818401526020810190506108c9565b50505050905090810190601f1680156109115780820380516001836020036101000a031916815260200191505b509250505060405180910390f35b6109276116cf565b6040518082815260200191505060405180910390f35b61098b6004803603604081101561095357600080fd5b81019080803573ffffffffffffffffffffffffffffffffffffffff1690602001909291908035151590602001909291905050506116d6565b005b610a90600480360360808110156109a357600080fd5b81019080803573ffffffffffffffffffffffffffffffffffffffff169060200190929190803573ffffffffffffffffffffffffffffffffffffffff1690602001909291908035906020019092919080359060200190640100000000811115610a0a57600080fd5b820183602082011115610a1c57600080fd5b80359060200191846001830284011164010000000083111715610a3e57600080fd5b91908080601f016020809104026020016040519081016040528093929190818152602001838380828437600081840152601f19601f82011690508083019250505050505050919291929050505061188c565b005b610abe60048036036020811015610aa857600080fd5b8101908080359060200190929190505050611904565b6040518080602001828103825283818151815260200191508051906020019080838360005b83811015610afe578082015181840152602081019050610ae3565b50505050905090810190601f168015610b2b5780820380516001836020036101000a031916815260200191505b509250505060405180910390f35b610b6560048036036020811015610b4f57600080fd5b8101908080359060200190929190505050611bd5565b6040518082815260200191505060405180910390f35b610b83611bfb565b6040518082815260200191505060405180910390f35b610be560048036036040811015610baf57600080fd5b8101908080359060200190929190803573ffffffffffffffffffffffffffffffffffffffff169060200190929190505050611c1f565b005b610bef611ca8565b6040518082815260200191505060405180910390f35b610c6760048036036040811015610c1b57600080fd5b81019080803573ffffffffffffffffffffffffffffffffffffffff169060200190929190803573ffffffffffffffffffffffffffffffffffffffff169060200190929190505050611ccc565b60405180821515815260200191505060405180910390f35b600060016000837bffffffffffffffffffffffffffffffffffffffffffffffffffffffff19167bffffffffffffffffffffffffffffffffffffffffffffffffffffffff1916815260200190815260200160002060009054906101000a900460ff169050919050565b606060078054600181600116156101000203166002900480601f016020809104026020016040519081016040528092919081815260200182805460018160011615610100020316600290048015610d7f5780601f10610d5457610100808354040283529160200191610d7f565b820191906000526020600020905b815481529060010190602001808311610d6257829003601f168201915b5050505050905090565b6000610d9482611d90565b610de9576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040180806020018281038252602c815260200180613910602c913960400191505060405180910390fd5b6005600083815260200190815260200160002060009054906101000a900473ffffffffffffffffffffffffffffffffffffffff169050919050565b6000610e2f826112e7565b90508073ffffffffffffffffffffffffffffffffffffffff168373ffffffffffffffffffffffffffffffffffffffff161415610eb6576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260218152602001806139946021913960400191505060405180910390fd5b8073ffffffffffffffffffffffffffffffffffffffff16610ed5611dad565b73ffffffffffffffffffffffffffffffffffffffff161480610f045750610f0381610efe611dad565b611ccc565b5b610f59576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260388152602001806138636038913960400191505060405180910390fd5b610f638383611db5565b505050565b6000610f746003611e6e565b905090565b610f8a610f84611dad565b82611e83565b610fdf576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260318152602001806139b56031913960400191505060405180910390fd5b610fea838383611f77565b505050565b6000806000838152602001908152602001600020600201549050919050565b6110346000808481526020019081526020016000206002015461102f611dad565b6115fc565b611089576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040180806020018281038252602f81526020018061371e602f913960400191505060405180910390fd5b61109382826121ba565b5050565b60006110ea82600260008673ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002061224d90919063ffffffff16565b905092915050565b6110fa611dad565b73ffffffffffffffffffffffffffffffffffffffff168173ffffffffffffffffffffffffffffffffffffffff161461117d576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040180806020018281038252602f815260200180613a93602f913960400191505060405180910390fd5b6111878282612267565b5050565b6111bc7f65d7a28e3265b37a6474929f336521b332c1681b933f6cb9f3376673440d862a6111b7611dad565b6115fc565b611211576040517f08c379a0000000000000000000000000000000000000000000000000000000008152600401808060200182810382526040815260200180613a536040913960400191505060405180910390fd5b6112196122fa565b565b6112368383836040518060200160405280600081525061188c565b505050565b61124c611246611dad565b82611e83565b6112a1576040517f08c379a0000000000000000000000000000000000000000000000000000000008152600401808060200182810382526030815260200180613a236030913960400191505060405180910390fd5b6112aa816123e5565b50565b6000806112c483600361251f90919063ffffffff16565b50905080915050919050565b6000600b60009054906101000a900460ff16905090565b6000611317826040518060600160405280602981526020016138c560299139600361254b9092919063ffffffff16565b9050919050565b61134f7f9f2df0fed2c77648de5860a4cc508cd0818c85b8b8a1ab4ceeef8d981c8956a661134a611dad565b6115fc565b6113a4576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040180806020018281038252603d8152602001806139e6603d913960400191505060405180910390fd5b6113b7816113b2600c61256a565b612578565b6113c1600c61276c565b50565b6060600a8054600181600116156101000203166002900480601f01602080910402602001604051908101604052809291908181526020018280546001816001161561010002031660029004801561145c5780601f106114315761010080835404028352916020019161145c565b820191906000526020600020905b81548152906001019060200180831161143f57829003601f168201915b5050505050905090565b60008073ffffffffffffffffffffffffffffffffffffffff168273ffffffffffffffffffffffffffffffffffffffff1614156114ed576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040180806020018281038252602a81526020018061389b602a913960400191505060405180910390fd5b611534600260008473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff168152602001908152602001600020612782565b9050919050565b61156c7f65d7a28e3265b37a6474929f336521b332c1681b933f6cb9f3376673440d862a611567611dad565b6115fc565b6115c1576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040180806020018281038252603e81526020018061377f603e913960400191505060405180910390fd5b6115c9612797565b565b60006115f48260008086815260200190815260200160002060000161288390919063ffffffff16565b905092915050565b60006116258260008086815260200190815260200160002060000161289d90919063ffffffff16565b905092915050565b606060088054600181600116156101000203166002900480601f0160208091040260200160405190810160405280929190818152602001828054600181600116156101000203166002900480156116c55780601f1061169a576101008083540402835291602001916116c5565b820191906000526020600020905b8154815290600101906020018083116116a857829003601f168201915b5050505050905090565b6000801b81565b6116de611dad565b73ffffffffffffffffffffffffffffffffffffffff168273ffffffffffffffffffffffffffffffffffffffff16141561177f576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260198152602001807f4552433732313a20617070726f766520746f2063616c6c65720000000000000081525060200191505060405180910390fd5b806006600061178c611dad565b73ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060008473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060006101000a81548160ff0219169083151502179055508173ffffffffffffffffffffffffffffffffffffffff16611839611dad565b73ffffffffffffffffffffffffffffffffffffffff167f17307eab39ab6107e8899845ad3d59bd9653f200f220920489ca2b5937696c318360405180821515815260200191505060405180910390a35050565b61189d611897611dad565b83611e83565b6118f2576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260318152602001806139b56031913960400191505060405180910390fd5b6118fe848484846128cd565b50505050565b606061190f82611d90565b611964576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040180806020018281038252602f815260200180613965602f913960400191505060405180910390fd5b6060600960008481526020019081526020016000208054600181600116156101000203166002900480601f016020809104026020016040519081016040528092919081815260200182805460018160011615610100020316600290048015611a0d5780601f106119e257610100808354040283529160200191611a0d565b820191906000526020600020905b8154815290600101906020018083116119f057829003601f168201915b505050505090506060611a1e6113c4565b9050600081511415611a34578192505050611bd0565b600082511115611b055780826040516020018083805190602001908083835b60208310611a765780518252602082019150602081019050602083039250611a53565b6001836020036101000a03801982511681845116808217855250505050505090500182805190602001908083835b60208310611ac75780518252602082019150602081019050602083039250611aa4565b6001836020036101000a0380198251168184511680821785525050505050509050019250505060405160208183030381529060405292505050611bd0565b80611b0f8561293f565b6040516020018083805190602001908083835b60208310611b455780518252602082019150602081019050602083039250611b22565b6001836020036101000a03801982511681845116808217855250505050505090500182805190602001908083835b60208310611b965780518252602082019150602081019050602083039250611b73565b6001836020036101000a03801982511681845116808217855250505050505090500192505050604051602081830303815290604052925050505b919050565b6000611bf4600080848152602001908152602001600020600001612a86565b9050919050565b7f9f2df0fed2c77648de5860a4cc508cd0818c85b8b8a1ab4ceeef8d981c8956a681565b611c4560008084815260200190815260200160002060020154611c40611dad565b6115fc565b611c9a576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260308152602001806138336030913960400191505060405180910390fd5b611ca48282612267565b5050565b7f65d7a28e3265b37a6474929f336521b332c1681b933f6cb9f3376673440d862a81565b6000600660008473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060008373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060009054906101000a900460ff16905092915050565b6000611d88836000018373ffffffffffffffffffffffffffffffffffffffff1660001b612a9b565b905092915050565b6000611da6826003612b0b90919063ffffffff16565b9050919050565b600033905090565b816005600083815260200190815260200160002060006101000a81548173ffffffffffffffffffffffffffffffffffffffff021916908373ffffffffffffffffffffffffffffffffffffffff160217905550808273ffffffffffffffffffffffffffffffffffffffff16611e28836112e7565b73ffffffffffffffffffffffffffffffffffffffff167f8c5be1e5ebec7d5bd14f71427d1e84f3dd0314c0f7b2291e5b200ac8c7c3b92560405160405180910390a45050565b6000611e7c82600001612b25565b9050919050565b6000611e8e82611d90565b611ee3576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040180806020018281038252602c815260200180613807602c913960400191505060405180910390fd5b6000611eee836112e7565b90508073ffffffffffffffffffffffffffffffffffffffff168473ffffffffffffffffffffffffffffffffffffffff161480611f5d57508373ffffffffffffffffffffffffffffffffffffffff16611f4584610d89565b73ffffffffffffffffffffffffffffffffffffffff16145b80611f6e5750611f6d8185611ccc565b5b91505092915050565b8273ffffffffffffffffffffffffffffffffffffffff16611f97826112e7565b73ffffffffffffffffffffffffffffffffffffffff1614612003576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040180806020018281038252602981526020018061393c6029913960400191505060405180910390fd5b600073ffffffffffffffffffffffffffffffffffffffff168273ffffffffffffffffffffffffffffffffffffffff161415612089576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260248152602001806137bd6024913960400191505060405180910390fd5b612094838383612b36565b61209f600082611db5565b6120f081600260008673ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff168152602001908152602001600020612b4690919063ffffffff16565b5061214281600260008573ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff168152602001908152602001600020612b6090919063ffffffff16565b5061215981836003612b7a9092919063ffffffff16565b50808273ffffffffffffffffffffffffffffffffffffffff168473ffffffffffffffffffffffffffffffffffffffff167fddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef60405160405180910390a4505050565b6121e181600080858152602001908152602001600020600001611d6090919063ffffffff16565b15612249576121ee611dad565b73ffffffffffffffffffffffffffffffffffffffff168173ffffffffffffffffffffffffffffffffffffffff16837f2f8788117e7eff1d82e926ec794901d17c78024a50270940304540a733656f0d60405160405180910390a45b5050565b600061225c8360000183612baf565b60001c905092915050565b61228e81600080858152602001908152602001600020600001612c3290919063ffffffff16565b156122f65761229b611dad565b73ffffffffffffffffffffffffffffffffffffffff168173ffffffffffffffffffffffffffffffffffffffff16837ff6391f5c32d9c69d2a47ea670b442974b53935d1edc7fd64eb21e047a839171b60405160405180910390a45b5050565b6123026112d0565b612374576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260148152602001807f5061757361626c653a206e6f742070617573656400000000000000000000000081525060200191505060405180910390fd5b6000600b60006101000a81548160ff0219169083151502179055507f5db9ee0a495bf2e6ff9c91a7834c1ba4fdd244a5e8aa4e537bd38aeae4b073aa6123b8611dad565b604051808273ffffffffffffffffffffffffffffffffffffffff16815260200191505060405180910390a1565b60006123f0826112e7565b90506123fe81600084612b36565b612409600083611db5565b6000600960008481526020019081526020016000208054600181600116156101000203166002900490501461245857600960008381526020019081526020016000206000612457919061366b565b5b6124a982600260008473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff168152602001908152602001600020612b4690919063ffffffff16565b506124be826003612c6290919063ffffffff16565b5081600073ffffffffffffffffffffffffffffffffffffffff168273ffffffffffffffffffffffffffffffffffffffff167fddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef60405160405180910390a45050565b6000806000806125328660000186612c7c565b915091508160001c8160001c9350935050509250929050565b600061255e846000018460001b84612d15565b60001c90509392505050565b600081600001549050919050565b600073ffffffffffffffffffffffffffffffffffffffff168273ffffffffffffffffffffffffffffffffffffffff16141561261b576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260208152602001807f4552433732313a206d696e7420746f20746865207a65726f206164647265737381525060200191505060405180910390fd5b61262481611d90565b15612697576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040180806020018281038252601c8152602001807f4552433732313a20746f6b656e20616c7265616479206d696e7465640000000081525060200191505060405180910390fd5b6126a360008383612b36565b6126f481600260008573ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff168152602001908152602001600020612b6090919063ffffffff16565b5061270b81836003612b7a9092919063ffffffff16565b50808273ffffffffffffffffffffffffffffffffffffffff16600073ffffffffffffffffffffffffffffffffffffffff167fddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef60405160405180910390a45050565b6001816000016000828254019250508190555050565b600061279082600001612e0b565b9050919050565b61279f6112d0565b15612812576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260108152602001807f5061757361626c653a207061757365640000000000000000000000000000000081525060200191505060405180910390fd5b6001600b60006101000a81548160ff0219169083151502179055507f62e78cea01bee320cd4e420270b5ea74000d11b0c9f74754ebdbfc544b05a258612856611dad565b604051808273ffffffffffffffffffffffffffffffffffffffff16815260200191505060405180910390a1565b60006128928360000183612baf565b60001c905092915050565b60006128c5836000018373ffffffffffffffffffffffffffffffffffffffff1660001b612e1c565b905092915050565b6128d8848484611f77565b6128e484848484612e3f565b612939576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040180806020018281038252603281526020018061374d6032913960400191505060405180910390fd5b50505050565b60606000821415612987576040518060400160405280600181526020017f30000000000000000000000000000000000000000000000000000000000000008152509050612a81565b600082905060005b600082146129b1578080600101915050600a82816129a957fe5b04915061298f565b60608167ffffffffffffffff811180156129ca57600080fd5b506040519080825280601f01601f1916602001820160405280156129fd5781602001600182028036833780820191505090505b50905060006001830390508593505b60008414612a7957600a8481612a1e57fe5b0660300160f81b82828060019003935081518110612a3857fe5b60200101907effffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff1916908160001a905350600a8481612a7157fe5b049350612a0c565b819450505050505b919050565b6000612a9482600001612e0b565b9050919050565b6000612aa78383612e1c565b612b00578260000182908060018154018082558091505060019003906000526020600020016000909190919091505582600001805490508360010160008481526020019081526020016000208190555060019050612b05565b600090505b92915050565b6000612b1d836000018360001b613058565b905092915050565b600081600001805490509050919050565b612b4183838361307b565b505050565b6000612b58836000018360001b6130e9565b905092915050565b6000612b72836000018360001b612a9b565b905092915050565b6000612ba6846000018460001b8473ffffffffffffffffffffffffffffffffffffffff1660001b6131d1565b90509392505050565b600081836000018054905011612c10576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260228152602001806136d16022913960400191505060405180910390fd5b826000018281548110612c1f57fe5b9060005260206000200154905092915050565b6000612c5a836000018373ffffffffffffffffffffffffffffffffffffffff1660001b6130e9565b905092915050565b6000612c74836000018360001b6132ad565b905092915050565b60008082846000018054905011612cde576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260228152602001806138ee6022913960400191505060405180910390fd5b6000846000018481548110612cef57fe5b906000526020600020906002020190508060000154816001015492509250509250929050565b60008084600101600085815260200190815260200160002054905060008114158390612ddc576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825283818151815260200191508051906020019080838360005b83811015612da1578082015181840152602081019050612d86565b50505050905090810190601f168015612dce5780820380516001836020036101000a031916815260200191505b509250505060405180910390fd5b50846000016001820381548110612def57fe5b9060005260206000209060020201600101549150509392505050565b600081600001805490509050919050565b600080836001016000848152602001908152602001600020541415905092915050565b6000612e608473ffffffffffffffffffffffffffffffffffffffff166133c6565b612e6d5760019050613050565b6060612fd763150b7a0260e01b612e82611dad565b888787604051602401808573ffffffffffffffffffffffffffffffffffffffff1681526020018473ffffffffffffffffffffffffffffffffffffffff16815260200183815260200180602001828103825283818151815260200191508051906020019080838360005b83811015612f06578082015181840152602081019050612eeb565b50505050905090810190601f168015612f335780820380516001836020036101000a031916815260200191505b5095505050505050604051602081830303815290604052907bffffffffffffffffffffffffffffffffffffffffffffffffffffffff19166020820180517bffffffffffffffffffffffffffffffffffffffffffffffffffffffff838183161783525050505060405180606001604052806032815260200161374d603291398773ffffffffffffffffffffffffffffffffffffffff166133d99092919063ffffffff16565b90506000818060200190516020811015612ff057600080fd5b8101908080519060200190929190505050905063150b7a0260e01b7bffffffffffffffffffffffffffffffffffffffffffffffffffffffff1916817bffffffffffffffffffffffffffffffffffffffffffffffffffffffff191614925050505b949350505050565b600080836001016000848152602001908152602001600020541415905092915050565b6130868383836133f1565b61308e6112d0565b156130e4576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040180806020018281038252602b8152602001806136f3602b913960400191505060405180910390fd5b505050565b600080836001016000848152602001908152602001600020549050600081146131c5576000600182039050600060018660000180549050039050600086600001828154811061313457fe5b906000526020600020015490508087600001848154811061315157fe5b906000526020600020018190555060018301876001016000838152602001908152602001600020819055508660000180548061318957fe5b600190038181906000526020600020016000905590558660010160008781526020019081526020016000206000905560019450505050506131cb565b60009150505b92915050565b6000808460010160008581526020019081526020016000205490506000811415613278578460000160405180604001604052808681526020018581525090806001815401808255809150506001900390600052602060002090600202016000909190919091506000820151816000015560208201518160010155505084600001805490508560010160008681526020019081526020016000208190555060019150506132a6565b8285600001600183038154811061328b57fe5b90600052602060002090600202016001018190555060009150505b9392505050565b600080836001016000848152602001908152602001600020549050600081146133ba57600060018203905060006001866000018054905003905060008660000182815481106132f857fe5b906000526020600020906002020190508087600001848154811061331857fe5b906000526020600020906002020160008201548160000155600182015481600101559050506001830187600101600083600001548152602001908152602001600020819055508660000180548061336b57fe5b60019003818190600052602060002090600202016000808201600090556001820160009055505090558660010160008781526020019081526020016000206000905560019450505050506133c0565b60009150505b92915050565b600080823b905060008111915050919050565b60606133e884846000856133f6565b90509392505050565b505050565b606082471015613451576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260268152602001806137e16026913960400191505060405180910390fd5b61345a856133c6565b6134cc576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040180806020018281038252601d8152602001807f416464726573733a2063616c6c20746f206e6f6e2d636f6e747261637400000081525060200191505060405180910390fd5b600060608673ffffffffffffffffffffffffffffffffffffffff1685876040518082805190602001908083835b6020831061351c57805182526020820191506020810190506020830392506134f9565b6001836020036101000a03801982511681845116808217855250505050505090500191505060006040518083038185875af1925050503d806000811461357e576040519150601f19603f3d011682016040523d82523d6000602084013e613583565b606091505b509150915061359382828661359f565b92505050949350505050565b606083156135af57829050613664565b6000835111156135c25782518084602001fd5b816040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825283818151815260200191508051906020019080838360005b8381101561362957808201518184015260208101905061360e565b50505050905090810190601f1680156136565780820380516001836020036101000a031916815260200191505b509250505060405180910390fd5b9392505050565b50805460018160011615610100020316600290046000825580601f1061369157506136b0565b601f0160209004906000526020600020908101906136af91906136b3565b5b50565b5b808211156136cc5760008160009055506001016136b4565b509056fe456e756d657261626c655365743a20696e646578206f7574206f6620626f756e64734552433732315061757361626c653a20746f6b656e207472616e73666572207768696c6520706175736564416363657373436f6e74726f6c3a2073656e646572206d75737420626520616e2061646d696e20746f206772616e744552433732313a207472616e7366657220746f206e6f6e20455243373231526563656976657220696d706c656d656e7465724552433732315072657365744d696e7465725061757365724175746f49643a206d75737420686176652070617573657220726f6c6520746f2070617573654552433732313a207472616e7366657220746f20746865207a65726f2061646472657373416464726573733a20696e73756666696369656e742062616c616e636520666f722063616c6c4552433732313a206f70657261746f7220717565727920666f72206e6f6e6578697374656e7420746f6b656e416363657373436f6e74726f6c3a2073656e646572206d75737420626520616e2061646d696e20746f207265766f6b654552433732313a20617070726f76652063616c6c6572206973206e6f74206f776e6572206e6f7220617070726f76656420666f7220616c6c4552433732313a2062616c616e636520717565727920666f7220746865207a65726f20616464726573734552433732313a206f776e657220717565727920666f72206e6f6e6578697374656e7420746f6b656e456e756d657261626c654d61703a20696e646578206f7574206f6620626f756e64734552433732313a20617070726f76656420717565727920666f72206e6f6e6578697374656e7420746f6b656e4552433732313a207472616e73666572206f6620746f6b656e2074686174206973206e6f74206f776e4552433732314d657461646174613a2055524920717565727920666f72206e6f6e6578697374656e7420746f6b656e4552433732313a20617070726f76616c20746f2063757272656e74206f776e65724552433732313a207472616e736665722063616c6c6572206973206e6f74206f776e6572206e6f7220617070726f7665644552433732315072657365744d696e7465725061757365724175746f49643a206d7573742068617665206d696e74657220726f6c6520746f206d696e744552433732314275726e61626c653a2063616c6c6572206973206e6f74206f776e6572206e6f7220617070726f7665644552433732315072657365744d696e7465725061757365724175746f49643a206d75737420686176652070617573657220726f6c6520746f20756e7061757365416363657373436f6e74726f6c3a2063616e206f6e6c792072656e6f756e636520726f6c657320666f722073656c66a26469706673582212206a5d38a7ba72576f3c51e0a7f06995fd5a4a019e82550cb49ce10773b34a097b64736f6c634300060c0033"
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
                    				"internalType": "string",
                    				"name": "baseURI",
                    				"type": "string"
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
                    				"name": "approved",
                    				"type": "address"
                    			},
                    			{
                    				"indexed": True,
                    				"internalType": "uint256",
                    				"name": "tokenId",
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
                    				"name": "owner",
                    				"type": "address"
                    			},
                    			{
                    				"indexed": True,
                    				"internalType": "address",
                    				"name": "operator",
                    				"type": "address"
                    			},
                    			{
                    				"indexed": False,
                    				"internalType": "bool",
                    				"name": "approved",
                    				"type": "bool"
                    			}
                    		],
                    		"name": "ApprovalForAll",
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
                    				"internalType": "bytes32",
                    				"name": "role",
                    				"type": "bytes32"
                    			},
                    			{
                    				"indexed": True,
                    				"internalType": "bytes32",
                    				"name": "previousAdminRole",
                    				"type": "bytes32"
                    			},
                    			{
                    				"indexed": True,
                    				"internalType": "bytes32",
                    				"name": "newAdminRole",
                    				"type": "bytes32"
                    			}
                    		],
                    		"name": "RoleAdminChanged",
                    		"type": "event"
                    	},
                    	{
                    		"anonymous": False,
                    		"inputs": [
                    			{
                    				"indexed": True,
                    				"internalType": "bytes32",
                    				"name": "role",
                    				"type": "bytes32"
                    			},
                    			{
                    				"indexed": True,
                    				"internalType": "address",
                    				"name": "account",
                    				"type": "address"
                    			},
                    			{
                    				"indexed": True,
                    				"internalType": "address",
                    				"name": "sender",
                    				"type": "address"
                    			}
                    		],
                    		"name": "RoleGranted",
                    		"type": "event"
                    	},
                    	{
                    		"anonymous": False,
                    		"inputs": [
                    			{
                    				"indexed": True,
                    				"internalType": "bytes32",
                    				"name": "role",
                    				"type": "bytes32"
                    			},
                    			{
                    				"indexed": True,
                    				"internalType": "address",
                    				"name": "account",
                    				"type": "address"
                    			},
                    			{
                    				"indexed": True,
                    				"internalType": "address",
                    				"name": "sender",
                    				"type": "address"
                    			}
                    		],
                    		"name": "RoleRevoked",
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
                    				"indexed": True,
                    				"internalType": "uint256",
                    				"name": "tokenId",
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
                    		"inputs": [],
                    		"name": "DEFAULT_ADMIN_ROLE",
                    		"outputs": [
                    			{
                    				"internalType": "bytes32",
                    				"name": "",
                    				"type": "bytes32"
                    			}
                    		],
                    		"stateMutability": "view",
                    		"type": "function"
                    	},
                    	{
                    		"inputs": [],
                    		"name": "MINTER_ROLE",
                    		"outputs": [
                    			{
                    				"internalType": "bytes32",
                    				"name": "",
                    				"type": "bytes32"
                    			}
                    		],
                    		"stateMutability": "view",
                    		"type": "function"
                    	},
                    	{
                    		"inputs": [],
                    		"name": "PAUSER_ROLE",
                    		"outputs": [
                    			{
                    				"internalType": "bytes32",
                    				"name": "",
                    				"type": "bytes32"
                    			}
                    		],
                    		"stateMutability": "view",
                    		"type": "function"
                    	},
                    	{
                    		"inputs": [
                    			{
                    				"internalType": "address",
                    				"name": "to",
                    				"type": "address"
                    			},
                    			{
                    				"internalType": "uint256",
                    				"name": "tokenId",
                    				"type": "uint256"
                    			}
                    		],
                    		"name": "approve",
                    		"outputs": [],
                    		"stateMutability": "nonpayable",
                    		"type": "function"
                    	},
                    	{
                    		"inputs": [
                    			{
                    				"internalType": "address",
                    				"name": "owner",
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
                    		"inputs": [],
                    		"name": "baseURI",
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
                    		"inputs": [
                    			{
                    				"internalType": "uint256",
                    				"name": "tokenId",
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
                    				"internalType": "uint256",
                    				"name": "tokenId",
                    				"type": "uint256"
                    			}
                    		],
                    		"name": "getApproved",
                    		"outputs": [
                    			{
                    				"internalType": "address",
                    				"name": "",
                    				"type": "address"
                    			}
                    		],
                    		"stateMutability": "view",
                    		"type": "function"
                    	},
                    	{
                    		"inputs": [
                    			{
                    				"internalType": "bytes32",
                    				"name": "role",
                    				"type": "bytes32"
                    			}
                    		],
                    		"name": "getRoleAdmin",
                    		"outputs": [
                    			{
                    				"internalType": "bytes32",
                    				"name": "",
                    				"type": "bytes32"
                    			}
                    		],
                    		"stateMutability": "view",
                    		"type": "function"
                    	},
                    	{
                    		"inputs": [
                    			{
                    				"internalType": "bytes32",
                    				"name": "role",
                    				"type": "bytes32"
                    			},
                    			{
                    				"internalType": "uint256",
                    				"name": "index",
                    				"type": "uint256"
                    			}
                    		],
                    		"name": "getRoleMember",
                    		"outputs": [
                    			{
                    				"internalType": "address",
                    				"name": "",
                    				"type": "address"
                    			}
                    		],
                    		"stateMutability": "view",
                    		"type": "function"
                    	},
                    	{
                    		"inputs": [
                    			{
                    				"internalType": "bytes32",
                    				"name": "role",
                    				"type": "bytes32"
                    			}
                    		],
                    		"name": "getRoleMemberCount",
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
                    				"internalType": "bytes32",
                    				"name": "role",
                    				"type": "bytes32"
                    			},
                    			{
                    				"internalType": "address",
                    				"name": "account",
                    				"type": "address"
                    			}
                    		],
                    		"name": "grantRole",
                    		"outputs": [],
                    		"stateMutability": "nonpayable",
                    		"type": "function"
                    	},
                    	{
                    		"inputs": [
                    			{
                    				"internalType": "bytes32",
                    				"name": "role",
                    				"type": "bytes32"
                    			},
                    			{
                    				"internalType": "address",
                    				"name": "account",
                    				"type": "address"
                    			}
                    		],
                    		"name": "hasRole",
                    		"outputs": [
                    			{
                    				"internalType": "bool",
                    				"name": "",
                    				"type": "bool"
                    			}
                    		],
                    		"stateMutability": "view",
                    		"type": "function"
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
                    				"name": "operator",
                    				"type": "address"
                    			}
                    		],
                    		"name": "isApprovedForAll",
                    		"outputs": [
                    			{
                    				"internalType": "bool",
                    				"name": "",
                    				"type": "bool"
                    			}
                    		],
                    		"stateMutability": "view",
                    		"type": "function"
                    	},
                    	{
                    		"inputs": [
                    			{
                    				"internalType": "address",
                    				"name": "to",
                    				"type": "address"
                    			}
                    		],
                    		"name": "mint",
                    		"outputs": [],
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
                    		"inputs": [
                    			{
                    				"internalType": "uint256",
                    				"name": "tokenId",
                    				"type": "uint256"
                    			}
                    		],
                    		"name": "ownerOf",
                    		"outputs": [
                    			{
                    				"internalType": "address",
                    				"name": "",
                    				"type": "address"
                    			}
                    		],
                    		"stateMutability": "view",
                    		"type": "function"
                    	},
                    	{
                    		"inputs": [],
                    		"name": "pause",
                    		"outputs": [],
                    		"stateMutability": "nonpayable",
                    		"type": "function"
                    	},
                    	{
                    		"inputs": [],
                    		"name": "paused",
                    		"outputs": [
                    			{
                    				"internalType": "bool",
                    				"name": "",
                    				"type": "bool"
                    			}
                    		],
                    		"stateMutability": "view",
                    		"type": "function"
                    	},
                    	{
                    		"inputs": [
                    			{
                    				"internalType": "bytes32",
                    				"name": "role",
                    				"type": "bytes32"
                    			},
                    			{
                    				"internalType": "address",
                    				"name": "account",
                    				"type": "address"
                    			}
                    		],
                    		"name": "renounceRole",
                    		"outputs": [],
                    		"stateMutability": "nonpayable",
                    		"type": "function"
                    	},
                    	{
                    		"inputs": [
                    			{
                    				"internalType": "bytes32",
                    				"name": "role",
                    				"type": "bytes32"
                    			},
                    			{
                    				"internalType": "address",
                    				"name": "account",
                    				"type": "address"
                    			}
                    		],
                    		"name": "revokeRole",
                    		"outputs": [],
                    		"stateMutability": "nonpayable",
                    		"type": "function"
                    	},
                    	{
                    		"inputs": [
                    			{
                    				"internalType": "address",
                    				"name": "from",
                    				"type": "address"
                    			},
                    			{
                    				"internalType": "address",
                    				"name": "to",
                    				"type": "address"
                    			},
                    			{
                    				"internalType": "uint256",
                    				"name": "tokenId",
                    				"type": "uint256"
                    			}
                    		],
                    		"name": "safeTransferFrom",
                    		"outputs": [],
                    		"stateMutability": "nonpayable",
                    		"type": "function"
                    	},
                    	{
                    		"inputs": [
                    			{
                    				"internalType": "address",
                    				"name": "from",
                    				"type": "address"
                    			},
                    			{
                    				"internalType": "address",
                    				"name": "to",
                    				"type": "address"
                    			},
                    			{
                    				"internalType": "uint256",
                    				"name": "tokenId",
                    				"type": "uint256"
                    			},
                    			{
                    				"internalType": "bytes",
                    				"name": "_data",
                    				"type": "bytes"
                    			}
                    		],
                    		"name": "safeTransferFrom",
                    		"outputs": [],
                    		"stateMutability": "nonpayable",
                    		"type": "function"
                    	},
                    	{
                    		"inputs": [
                    			{
                    				"internalType": "address",
                    				"name": "operator",
                    				"type": "address"
                    			},
                    			{
                    				"internalType": "bool",
                    				"name": "approved",
                    				"type": "bool"
                    			}
                    		],
                    		"name": "setApprovalForAll",
                    		"outputs": [],
                    		"stateMutability": "nonpayable",
                    		"type": "function"
                    	},
                    	{
                    		"inputs": [
                    			{
                    				"internalType": "bytes4",
                    				"name": "interfaceId",
                    				"type": "bytes4"
                    			}
                    		],
                    		"name": "supportsInterface",
                    		"outputs": [
                    			{
                    				"internalType": "bool",
                    				"name": "",
                    				"type": "bool"
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
                    		"inputs": [
                    			{
                    				"internalType": "uint256",
                    				"name": "index",
                    				"type": "uint256"
                    			}
                    		],
                    		"name": "tokenByIndex",
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
                    				"name": "owner",
                    				"type": "address"
                    			},
                    			{
                    				"internalType": "uint256",
                    				"name": "index",
                    				"type": "uint256"
                    			}
                    		],
                    		"name": "tokenOfOwnerByIndex",
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
                    				"name": "tokenId",
                    				"type": "uint256"
                    			}
                    		],
                    		"name": "tokenURI",
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
                    				"name": "from",
                    				"type": "address"
                    			},
                    			{
                    				"internalType": "address",
                    				"name": "to",
                    				"type": "address"
                    			},
                    			{
                    				"internalType": "uint256",
                    				"name": "tokenId",
                    				"type": "uint256"
                    			}
                    		],
                    		"name": "transferFrom",
                    		"outputs": [],
                    		"stateMutability": "nonpayable",
                    		"type": "function"
                    	},
                    	{
                    		"inputs": [],
                    		"name": "unpause",
                    		"outputs": [],
                    		"stateMutability": "nonpayable",
                    		"type": "function"
                    	}
                    ]

if __name__ == '__main__':
   erc = Erc721("", "ether", "testnet")
   erc.connect()
   print(erc.status()[1]['data']['number'])
   print(erc.is_connected())
   # print(erc.get_functions())
   print(erc.exec_function('balanceOf', {'owner': ''}))
