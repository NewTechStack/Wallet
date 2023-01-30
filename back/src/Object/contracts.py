from web3 import Web3, exceptions, middleware
from web3.middleware import geth_poa_middleware
from web3.gas_strategies.time_based import fast_gas_price_strategy
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
                    "rpc": "https://matic-mumbai.chainstacklabs.com",
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

    def execute_transaction(self, transaction, owner_address, owner_key, mult_gas = 2, wait = True, sender=None):
        gas_cost = None
        owner = {
            "address": owner_address,
            "key": owner_key
        }
        wallet = owner if sender is None else sender
        if sender is not None:
            wallet['key'] = self.link.eth.account.from_mnemonic(
                wallet['mnemonic']
            ).key
        if not 'address' in wallet or not 'key' in wallet:
            return [False, "Invalid wallet", 500]
        for _ in range(10):
            try:
                gas_cost = transaction.estimateGas({'from': wallet['address']})
                break
            except exceptions.ContractLogicError:
                pass
        if gas_cost is None:
            return [False, "Invalid logic", 400]
        build = None
        g_price = 21
        gas_price = self.link.toWei(g_price, 'gwei') * mult_gas
        if wallet != owner:
            tx = {
                'chainId': self.link.eth.chain_id,
                'nonce': self.link.eth.getTransactionCount(owner['address'], "pending"),
                'to': wallet['address'],
                'value': gas_price * gas_cost,
                'gas': 2000000,
                'gasPrice': gas_price
            }
            signed_txn = self.link.eth.account.signTransaction(tx, private_key=owner['key'])
            txn = self.link.eth.sendRawTransaction(signed_txn.rawTransaction).hex()
            for _ in range(10):
                try:
                    self.link.eth.waitForTransactionReceipt(txn)
                    break
                except exceptions.TimeExhausted:
                    pass
        for _ in range(10):
            try:
                build = transaction.buildTransaction({
                  'from': wallet['address'],
                  'gas': gas_cost,
                  'gasPrice': gas_price,
                  'nonce': self.link.eth.getTransactionCount(wallet['address'], "pending")
                })
            except requests.exceptions.HTTPError:
                pass
        if build is None:
            return [False, "Can't connect to RPC", 404]
        signed_txn = self.link.eth.account.signTransaction(
            build,
            private_key = wallet['key']
        )
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
        data = {'result': data}
        return json.loads(json.dumps(dict(data), cls=HexJsonEncoder))['result']

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
        self.id = None
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

    def exec_function(self, name, kwargs, wait=True, sender=None):
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
        return self.execute_transaction(transaction, owner.address, owner.key, wait=wait, sender=sender)

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
        self.id = id
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

    def delete(self, id):
        contract = dict(self.red.get(id).delete().run())
        return [True, contract, None]

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
        contract = ERCX(address, abi, bytecode, network_type, network)
        contract.id = id
        return [True, contract, None]

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
class CMTAT(Contract):
    def __init__(self, address,  network_type = None, network = None):
         super().__init__(address, network_type = network_type, network = network)
         self.bytecode = "60c0604052306080523480156200001557600080fd5b50604051620066b1380380620066b1833981016040819052620000389162000b43565b6001600160a01b038a1660a0528862000064576200005e8989898989898989896200008c565b6200007c565b6101cb805460ff191660011790556200007c620001bf565b5050505050505050505062000dd5565b600054610100900460ff1615808015620000ad5750600054600160ff909116105b80620000dd5750620000ca306200026c60201b62002c9f1760201c565b158015620000dd575060005460ff166001145b620001465760405162461bcd60e51b815260206004820152602e60248201527f496e697469616c697a61626c653a20636f6e747261637420697320616c72656160448201526d191e481a5b9a5d1a585b1a5e995960921b60648201526084015b60405180910390fd5b6000805460ff1916600117905580156200016a576000805461ff0019166101001790555b6200017d8a8a8a8a8a8a8a8a8a6200027b565b8015620001b3576000805461ff001916905560405160018152600080516020620066918339815191529060200160405180910390a15b50505050505050505050565b600054610100900460ff1615620002295760405162461bcd60e51b815260206004820152602760248201527f496e697469616c697a61626c653a20636f6e747261637420697320696e697469604482015266616c697a696e6760c81b60648201526084016200013d565b60005460ff908116146200026a576000805460ff191660ff908117909155604051908152600080516020620066918339815191529060200160405180910390a15b565b6001600160a01b03163b151590565b600054610100900460ff16620002d75760405162461bcd60e51b815260206004820152602b60248201526000805160206200667183398151915260448201526a6e697469616c697a696e6760a81b60648201526084016200013d565b620002e1620003b5565b620002ed878762000411565b620002f7620003b5565b62000301620003b5565b6200030b6200048f565b62000315620003b5565b6200031f620004f7565b6200032a8362000561565b620003358862000618565b6200033f620003b5565b62000349620003b5565b62000353620003b5565b6200035f60006200068c565b62000369620003b5565b62000373620003b5565b6200037d620003b5565b62000387620003b5565b62000391620003b5565b6200039f85858484620006ff565b620003aa8962000794565b505050505050505050565b600054610100900460ff166200026a5760405162461bcd60e51b815260206004820152602b60248201526000805160206200667183398151915260448201526a6e697469616c697a696e6760a81b60648201526084016200013d565b600054610100900460ff166200046d5760405162461bcd60e51b815260206004820152602b60248201526000805160206200667183398151915260448201526a6e697469616c697a696e6760a81b60648201526084016200013d565b60ce6200047b838262000d09565b5060cf6200048a828262000d09565b505050565b600054610100900460ff16620004eb5760405162461bcd60e51b815260206004820152602b60248201526000805160206200667183398151915260448201526a6e697469616c697a696e6760a81b60648201526084016200013d565b6066805460ff19169055565b600054610100900460ff16620005535760405162461bcd60e51b815260206004820152602b60248201526000805160206200667183398151915260448201526a6e697469616c697a696e6760a81b60648201526084016200013d565b600061010081905561010155565b600054610100900460ff16620005bd5760405162461bcd60e51b815260206004820152602b60248201526000805160206200667183398151915260448201526a6e697469616c697a696e6760a81b60648201526084016200013d565b6001600160a01b038116156200061557603380546001600160a01b0319166001600160a01b0383169081179091556040517f9c4d5c11b88d1e3d9c7ad50900cb6d10ac72853248cdc85ca868fb772e62b44990600090a25b50565b600054610100900460ff16620006745760405162461bcd60e51b815260206004820152602b60248201526000805160206200667183398151915260448201526a6e697469616c697a696e6760a81b60648201526084016200013d565b6200068160008262000804565b6200061581620008ad565b600054610100900460ff16620006e85760405162461bcd60e51b815260206004820152602b60248201526000805160206200667183398151915260448201526a6e697469616c697a696e6760a81b60648201526084016200013d565b610392805460ff191660ff92909216919091179055565b600054610100900460ff166200075b5760405162461bcd60e51b815260206004820152602b60248201526000805160206200667183398151915260448201526a6e697469616c697a696e6760a81b60648201526084016200013d565b6101cc6200076a858262000d09565b506101cd6200077a848262000d09565b506101ce6200078a838262000d09565b506101cf55505050565b600054610100900460ff16620007f05760405162461bcd60e51b815260206004820152602b60248201526000805160206200667183398151915260448201526a6e697469616c697a696e6760a81b60648201526084016200013d565b6101cb805460ff1916911515919091179055565b6000828152610167602090815260408083206001600160a01b038516845290915290205460ff16620008a9576000828152610167602090815260408083206001600160a01b03851684529091529020805460ff1916600117905562000868620009e1565b6001600160a01b0316816001600160a01b0316837f2f8788117e7eff1d82e926ec794901d17c78024a50270940304540a733656f0d60405160405180910390a45b5050565b620008d97f973ef39d76cc2c6090feab1c030bec6ab5db557f64df047a4c4f9b5953cf1df38262000804565b620009057f9f2df0fed2c77648de5860a4cc508cd0818c85b8b8a1ab4ceeef8d981c8956a68262000804565b620009317f3c11d16cbaffd01df69ce1c404f6340ee057498f5f00246190ea54220576a8488262000804565b6200095d7f65d7a28e3265b37a6474929f336521b332c1681b933f6cb9f3376673440d862a8262000804565b620009897f809a0fc49fc0600540f1d39e23454e1f6f215bc7505fa22b17c154616570ddef8262000804565b620009b57fc6f3350ab30f55ce45863160fc345c1663d4633fe7cacfd3b9bbb6420a9147f88262000804565b620006157faa2de0737115053bf7d3d68e733306557628aef4b4aefa746cbf344fc72672478262000804565b6000620009f8620009fd60201b62002cae1760201c565b905090565b6000620009f862000a1460201b62002cb41760201c565b60a0516000906001600160a01b0316330362000a37575060131936013560601c90565b620009f862000a4c60201b62002cf81760201c565b3390565b80516001600160a01b038116811462000a6857600080fd5b919050565b8051801515811462000a6857600080fd5b634e487b7160e01b600052604160045260246000fd5b600082601f83011262000aa657600080fd5b81516001600160401b038082111562000ac35762000ac362000a7e565b604051601f8301601f19908116603f0116810190828211818310171562000aee5762000aee62000a7e565b8160405283815260209250868385880101111562000b0b57600080fd5b600091505b8382101562000b2f578582018301518183018401529082019062000b10565b600093810190920192909252949350505050565b6000806000806000806000806000806101408b8d03121562000b6457600080fd5b62000b6f8b62000a50565b995062000b7f60208c0162000a6d565b985062000b8f60408c0162000a50565b60608c01519098506001600160401b038082111562000bad57600080fd5b62000bbb8e838f0162000a94565b985060808d015191508082111562000bd257600080fd5b62000be08e838f0162000a94565b975060a08d015191508082111562000bf757600080fd5b62000c058e838f0162000a94565b965060c08d015191508082111562000c1c57600080fd5b62000c2a8e838f0162000a94565b955062000c3a60e08e0162000a50565b94506101008d015191508082111562000c5257600080fd5b5062000c618d828e0162000a94565b9250506101208b015190509295989b9194979a5092959850565b600181811c9082168062000c9057607f821691505b60208210810362000cb157634e487b7160e01b600052602260045260246000fd5b50919050565b601f8211156200048a57600081815260208120601f850160051c8101602086101562000ce05750805b601f850160051c820191505b8181101562000d015782815560010162000cec565b505050505050565b81516001600160401b0381111562000d255762000d2562000a7e565b62000d3d8162000d36845462000c7b565b8462000cb7565b602080601f83116001811462000d75576000841562000d5c5750858301515b600019600386901b1c1916600185901b17855562000d01565b600085815260208120601f198616915b8281101562000da65788860151825594840194600190910190840162000d85565b508582101562000dc55787850151600019600388901b60f8161c191681555b5050505050600190811b01905550565b60805160a05161586f62000e02600039600081816106e80152612cb801526000613375015261586f6000f3fe608060405234801561001057600080fd5b50600436106104755760003560e01c806370a0823111610257578063cdd8999211610146578063dcfd616f116100c3578063ea4a603a11610087578063ea4a603a14610a47578063f47b774014610a5a578063fb1cb59e14610a62578063fb78ed4014610a75578063fcf196b414610a7d57600080fd5b8063dcfd616f146109e6578063dd62ed3e146109f9578063e2d6f63414610a0c578063e63ab1e914610a1f578063e8e386c014610a3457600080fd5b8063d50256251161010a578063d502562514610990578063d539139314610998578063d547741f146109ad578063d7ffbbaa146109c0578063d82c927a146109d357600080fd5b8063cdd8999214610918578063d05166501461092b578063d21268ef14610957578063d40c79f01461096a578063d4ce14151461097d57600080fd5b8063a217fddf116101d4578063b958544611610198578063b9585446146108b3578063be370b4f146108c8578063c6946a12146108dd578063c6f5fa9e146108f0578063cc7c36fe1461090357600080fd5b8063a217fddf1461085f578063a312e15514610867578063a457c2d71461087a578063a4a0a3011461088d578063a9059cbb146108a057600080fd5b80638430d0111161021b5780638430d0111461081f5780638456cb5914610832578063890eba681461083a57806391d148541461084457806395d89b411461085757600080fd5b806370a08231146107aa5780637352f249146107d357806375bf8fe7146107e657806378f86afc146107f95780637f4ab1dd1461080c57600080fd5b806339509351116103735780635474dce9116102f05780635f84f302116102b45780635f84f302146107495780635fb39a241461075c578063634daf761461076f57806363783444146107825780636439fd751461079557600080fd5b80635474dce9146106c5578063572b6c05146106d85780635be7cc16146107185780635c975abb1461072b5780635ee7a9421461073657600080fd5b806341c0e1b51161033757806341c0e1b51461066d578063426a84931461067557806343581cff146106885780634b73d1f51461069b57806350101d84146106ae57600080fd5b806339509351146106195780633c07af0f1461062c5780633f4ba83a1461063f5780633f4f90671461064757806340c10f191461065a57600080fd5b8063246b72ec116104015780632d141c64116103c55780632d141c64146105b35780632e479e4f146105c65780632f2ff15d146105d9578063313ce567146105ec57806336568abe1461060657600080fd5b8063246b72ec1461053f578063248a9ca31461055457806325d19933146105785780632787fac01461058b578063282c51f31461059e57600080fd5b80630f7be016116104485780630f7be016146104ea57806317d70f7c146104ff57806318160ddd1461050757806323b872dd14610519578063244b59e31461052c57600080fd5b806301ffc9a71461047a57806306fdde03146104a2578063095ea7b3146104b75780630dca59c1146104ca575b600080fd5b61048d610488366004614b01565b610aa8565b60405190151581526020015b60405180910390f35b6104aa610adf565b6040516104999190614b7b565b61048d6104c5366004614bae565b610b71565b6104d2610b93565b6040516104999c9b9a99989796959493929190614bda565b6104fd6104f8366004614d88565b61112f565b005b6104aa61154f565b60cd545b604051908152602001610499565b61048d610527366004614f72565b6115de565b6104fd61053a366004614fb3565b6115f5565b61050b6000805160206157fa83398151915281565b61050b610562366004614fe7565b6000908152610167602052604090206001015490565b6104fd610586366004614fb3565b61166c565b6104fd610599366004614fb3565b6116d7565b61050b60008051602061575a83398151915281565b6104fd6105c1366004614fb3565b611742565b6104fd6105d4366004614fb3565b6117ad565b6104fd6105e7366004615000565b611818565b6105f4611843565b60405160ff9091168152602001610499565b6104fd610614366004615000565b611857565b61048d610627366004614bae565b6118ea565b6104fd61063a366004614fe7565b611916565b6104fd611937565b61048d610655366004615030565b61195a565b6104fd610668366004614bae565b611986565b6104fd6119f0565b61048d61068336600461507f565b611a23565b6104fd6106963660046150cd565b611aa7565b6104fd6106a9366004614fb3565b611b44565b6106b6611baf565b604051610499939291906150ea565b6104fd6106d33660046150cd565b611c55565b61048d6106e636600461510d565b7f00000000000000000000000000000000000000000000000000000000000000006001600160a01b0390811691161490565b6104fd61072636600461510d565b611cff565b60665460ff1661048d565b61050b610744366004614fe7565b611fe5565b6104fd610757366004614fe7565b612006565b6104fd61076a366004614fb3565b612053565b61050b61077d366004615000565b6120be565b6104fd610790366004614fb3565b612117565b61050b60008051602061581a83398151915281565b61050b6107b836600461510d565b6001600160a01b0316600090815260cb602052604090205490565b6104fd6107e1366004614fb3565b612182565b61048d6107f4366004615030565b6121ed565b6104fd610807366004614fb3565b612211565b6104aa61081a366004615139565b61226f565b6104fd61082d366004614fe7565b61233b565b6104fd61235c565b61050b6101cf5481565b61048d610852366004615000565b61237c565b6104aa6123a8565b61050b600081565b6104fd610875366004614fe7565b6123b7565b61048d610888366004614bae565b6123d8565b6104fd61089b36600461510d565b61245e565b61048d6108ae366004614bae565b6124b4565b61050b60008051602061577a83398151915281565b6108d06124cc565b6040516104999190615156565b61048d6108eb366004614f72565b612524565b6104fd6108fe366004614fb3565b61254a565b61050b6000805160206157da83398151915281565b6104fd610926366004614fe7565b6125b5565b61048d61093936600461510d565b6001600160a01b031660009081526098602052604090205460ff1690565b6104fd61096536600461519a565b612602565b6104fd610978366004614fe7565b612624565b6105f461098b366004614f72565b612664565b6104aa6126c9565b61050b6000805160206157ba83398151915281565b6104fd6109bb366004615000565b6126d7565b6104fd6109ce366004614fb3565b6126fd565b6104fd6109e1366004614fb3565b61275b565b6104fd6109f4366004614fb3565b6127c6565b61050b610a073660046151bc565b612824565b6104fd610a1a366004614bae565b61284f565b61050b60008051602061579a83398151915281565b6104fd610a423660046151ea565b6128ac565b6104fd610a5536600461524b565b6129c2565b6104aa612ae5565b6104fd610a70366004614fe7565b612af3565b6108d0612b14565b603354610a90906001600160a01b031681565b6040516001600160a01b039091168152602001610499565b60006001600160e01b03198216637965db0b60e01b1480610ad957506301ffc9a760e01b6001600160e01b03198316145b92915050565b606060ce8054610aee90615358565b80601f0160208091040260200160405190810160405280929190818152602001828054610b1a90615358565b8015610b675780601f10610b3c57610100808354040283529160200191610b67565b820191906000526020600020905b815481529060010190602001808311610b4a57829003601f168201915b5050505050905090565b600080610b7c612cfc565b9050610b89818585612d06565b5060019392505050565b6103c580546103c6546103c7805492939192610bae90615358565b80601f0160208091040260200160405190810160405280929190818152602001828054610bda90615358565b8015610c275780601f10610bfc57610100808354040283529160200191610c27565b820191906000526020600020905b815481529060010190602001808311610c0a57829003601f168201915b505050505090806003018054610c3c90615358565b80601f0160208091040260200160405190810160405280929190818152602001828054610c6890615358565b8015610cb55780601f10610c8a57610100808354040283529160200191610cb5565b820191906000526020600020905b815481529060010190602001808311610c9857829003601f168201915b505050505090806004018054610cca90615358565b80601f0160208091040260200160405190810160405280929190818152602001828054610cf690615358565b8015610d435780601f10610d1857610100808354040283529160200191610d43565b820191906000526020600020905b815481529060010190602001808311610d2657829003601f168201915b505050505090806005018054610d5890615358565b80601f0160208091040260200160405190810160405280929190818152602001828054610d8490615358565b8015610dd15780601f10610da657610100808354040283529160200191610dd1565b820191906000526020600020905b815481529060010190602001808311610db457829003601f168201915b505050505090806006018054610de690615358565b80601f0160208091040260200160405190810160405280929190818152602001828054610e1290615358565b8015610e5f5780601f10610e3457610100808354040283529160200191610e5f565b820191906000526020600020905b815481529060010190602001808311610e4257829003601f168201915b505050505090806007018054610e7490615358565b80601f0160208091040260200160405190810160405280929190818152602001828054610ea090615358565b8015610eed5780601f10610ec257610100808354040283529160200191610eed565b820191906000526020600020905b815481529060010190602001808311610ed057829003601f168201915b505050505090806008018054610f0290615358565b80601f0160208091040260200160405190810160405280929190818152602001828054610f2e90615358565b8015610f7b5780601f10610f5057610100808354040283529160200191610f7b565b820191906000526020600020905b815481529060010190602001808311610f5e57829003601f168201915b505050505090806009018054610f9090615358565b80601f0160208091040260200160405190810160405280929190818152602001828054610fbc90615358565b80156110095780601f10610fde57610100808354040283529160200191611009565b820191906000526020600020905b815481529060010190602001808311610fec57829003601f168201915b50505050509080600a01805461101e90615358565b80601f016020809104026020016040519081016040528092919081815260200182805461104a90615358565b80156110975780601f1061106c57610100808354040283529160200191611097565b820191906000526020600020905b81548152906001019060200180831161107a57829003601f168201915b50505050509080600b0180546110ac90615358565b80601f01602080910402602001604051908101604052809291908181526020018280546110d890615358565b80156111255780601f106110fa57610100808354040283529160200191611125565b820191906000526020600020905b81548152906001019060200180831161110857829003601f168201915b505050505090508c565b6000805160206157da83398151915261114781612e2a565b60408051610180810182528e8152602081018e90529081018c9052606081018b9052608081018a905260a0810189905260c0810188905260e0810187905261010081018690526101208101859052610140810184905261016081018390526103c58e81556103c68e90556103c76111be8e826153e0565b50606082015160038201906111d390826153e0565b50608082015160048201906111e890826153e0565b5060a082015160058201906111fd90826153e0565b5060c0820151600682019061121290826153e0565b5060e0820151600782019061122790826153e0565b50610100820151600882019061123d90826153e0565b50610120820151600982019061125390826153e0565b50610140820151600a82019061126990826153e0565b50610160820151600b82019061127f90826153e0565b50506040518e91507f532f252238b3b0d2b8c8a257b087fb3fdbdc775e3e0acca8e680a2f36aafa34b90600090a26040518c907f5e2a471fe68796ada631b0f19c39a3d5665c59832c0e059f03e5c3fa3a86bbc290600090a28a6040516112e6919061549f565b60405180910390207f3621f0b03830d621e49f38b4a8a097e7f9f9af2f9b744754948cd539a8d981c18c60405161131d9190614b7b565b60405180910390a289604051611333919061549f565b60405180910390207fabdeeca66a0b3a7be7757e4cba2924e3461d017778692abfa039e0858a992a318b60405161136a9190614b7b565b60405180910390a288604051611380919061549f565b60405180910390207fd6f0388386cbb93ddbdb02bbf9d392681e6293695a78f8c365e52fb8f4f7ad0f8a6040516113b79190614b7b565b60405180910390a2876040516113cd919061549f565b60405180910390207f8455f5046de4a823b3559671d389aa0642c7e96db280bf12ece34ed6dbfc9d9b896040516114049190614b7b565b60405180910390a28660405161141a919061549f565b60405180910390207f1bcb2cc6a051bf8e937bfdae2d991a1b11f4e750bbdcb3495bc36d7c7ab5f161886040516114519190614b7b565b60405180910390a285604051611467919061549f565b60405180910390207f96a7193a2377a895adeb94c58ef4ddb419fa14a938e30cdc763cce1f1de636ea8760405161149e9190614b7b565b60405180910390a2846040516114b4919061549f565b60405180910390207f8528a756683d9ff1c2f830fdf4673cf4da5e5d3451715d83a2b29835b419ce30866040516114eb9190614b7b565b60405180910390a283604051611501919061549f565b60405180910390207feaf62d4185304a4e8817f1f9cfaeb93d62be036aef19ba6193c8b701a111c6ba856040516115389190614b7b565b60405180910390a250505050505050505050505050565b6101cc805461155d90615358565b80601f016020809104026020016040519081016040528092919081815260200182805461158990615358565b80156115d65780601f106115ab576101008083540402835291602001916115d6565b820191906000526020600020905b8154815290600101906020018083116115b957829003601f168201915b505050505081565b60006115eb848484612e3b565b90505b9392505050565b6000805160206157da83398151915261160d81612e2a565b6103d061161a83826153e0565b5081604051611629919061549f565b60405180910390207f4faee16800cb0902d3973cedb0ad4d0bc0d207d9a225afa3d2c64a2ee9dd70c3836040516116609190614b7b565b60405180910390a25050565b6000805160206157da83398151915261168481612e2a565b6103ce61169183826153e0565b50816040516116a0919061549f565b60405180910390207feaf62d4185304a4e8817f1f9cfaeb93d62be036aef19ba6193c8b701a111c6ba836040516116609190614b7b565b6000805160206157da8339815191526116ef81612e2a565b6103c96116fc83826153e0565b508160405161170b919061549f565b60405180910390207fd6f0388386cbb93ddbdb02bbf9d392681e6293695a78f8c365e52fb8f4f7ad0f836040516116609190614b7b565b6000805160206157da83398151915261175a81612e2a565b6103c861176783826153e0565b5081604051611776919061549f565b60405180910390207fabdeeca66a0b3a7be7757e4cba2924e3461d017778692abfa039e0858a992a31836040516116609190614b7b565b6000805160206157da8339815191526117c581612e2a565b6103cc6117d283826153e0565b50816040516117e1919061549f565b60405180910390207f96a7193a2377a895adeb94c58ef4ddb419fa14a938e30cdc763cce1f1de636ea836040516116609190614b7b565b6000828152610167602052604090206001015461183481612e2a565b61183e8383612eb1565b505050565b60006118526103925460ff1690565b905090565b61185f612cfc565b6001600160a01b0316816001600160a01b0316146118dc5760405162461bcd60e51b815260206004820152602f60248201527f416363657373436f6e74726f6c3a2063616e206f6e6c792072656e6f756e636560448201526e103937b632b9903337b91039b2b63360891b60648201526084015b60405180910390fd5b6118e68282612f39565b5050565b6000806118f5612cfc565b9050610b898185856119078589612824565b61191191906154d1565b612d06565b6000805160206157fa83398151915261192e81612e2a565b6118e682612fbf565b60008051602061579a83398151915261194f81612e2a565b611957613189565b50565b600060008051602061581a83398151915261197481612e2a565b61197e84846131e1565b949350505050565b6000805160206157ba83398151915261199e81612e2a565b6119a8838361329e565b826001600160a01b03167f0f6798a560793a54c3bcfe86a93cde1e73087d944c0ea20544137d4121396885836040516119e391815260200190565b60405180910390a2505050565b60006119fb81612e2a565b6101cb5460ff168015611a1057611a1061336b565b611a18612cfc565b6001600160a01b0316ff5b600081611a37611a31612cfc565b86612824565b14611a925760405162461bcd60e51b815260206004820152602560248201527f434d5441543a2063757272656e7420616c6c6f77616e6365206973206e6f74206044820152641c9a59da1d60da1b60648201526084016118d3565b611a9c8484610b71565b506001949350505050565b60008051602061577a833981519152611abf81612e2a565b6104035460ff16151582151503611b055760405162461bcd60e51b815260206004820152600a60248201526953616d652076616c756560b01b60448201526064016118d3565b610403805460ff19168315159081179091556040517fe241461ce7474b6fe1c3f8aaa4150fc7545522186efe4ca13ff14ea90db3120090600090a25050565b60008051602061577a833981519152611b5c81612e2a565b610404611b6983826153e0565b5081604051611b78919061549f565b60405180910390207f3050dc30d1115cd7dc7dadd07203d3151a941499e2c1609526139e2adfb43162836040516116609190614b7b565b6104038054610404805460ff8084169461010090940416929190611bd290615358565b80601f0160208091040260200160405190810160405280929190818152602001828054611bfe90615358565b8015611c4b5780601f10611c2057610100808354040283529160200191611c4b565b820191906000526020600020905b815481529060010190602001808311611c2e57829003601f168201915b5050505050905083565b60008051602061577a833981519152611c6d81612e2a565b61040354610100900460ff16151582151503611cb85760405162461bcd60e51b815260206004820152600a60248201526953616d652076616c756560b01b60448201526064016118d3565b610403805461ff001916610100841515908102919091179091556040517f542f36cc291fb3c7480ccc6fe5355dc6f63d22767c8df4020b547c6536c3795c90600090a25050565b6000611d0a81612e2a565b6001600160a01b038216611d585760405162461bcd60e51b81526020600482015260156024820152741059191c995cdcc80c081b9bdd08185b1b1bddd959605a1b60448201526064016118d3565b6000611d62612cfc565b9050826001600160a01b0316816001600160a01b031603611db45760405162461bcd60e51b815260206004820152600c60248201526b53616d65206164647265737360a01b60448201526064016118d3565b611dbf600084611818565b611dd760008051602061581a8339815191528261237c565b15611e0c57611df460008051602061581a83398151915284611818565b611e0c60008051602061581a83398151915282611857565b611e246000805160206157ba8339815191528261237c565b15611e5957611e416000805160206157ba83398151915284611818565b611e596000805160206157ba83398151915282611857565b611e7160008051602061575a8339815191528261237c565b15611ea657611e8e60008051602061575a83398151915284611818565b611ea660008051602061575a83398151915282611857565b611ebe60008051602061579a8339815191528261237c565b15611ef357611edb60008051602061579a83398151915284611818565b611ef360008051602061579a83398151915282611857565b611f0b6000805160206157fa8339815191528261237c565b15611f4057611f286000805160206157fa83398151915284611818565b611f406000805160206157fa83398151915282611857565b611f586000805160206157da8339815191528261237c565b15611f8d57611f756000805160206157da83398151915284611818565b611f8d6000805160206157da83398151915282611857565b611fa560008051602061577a8339815191528261237c565b15611fda57611fc260008051602061577a83398151915284611818565b611fda60008051602061577a83398151915282611857565b61183e600082611857565b6000806000611ff58460fe6133fb565b91509150816115ee5760cd5461197e565b6000805160206157da83398151915261201e81612e2a565b6103c582905560405182907f532f252238b3b0d2b8c8a257b087fb3fdbdc775e3e0acca8e680a2f36aafa34b90600090a25050565b6000805160206157da83398151915261206b81612e2a565b6103c761207883826153e0565b5081604051612087919061549f565b60405180910390207f3621f0b03830d621e49f38b4a8a097e7f9f9af2f9b744754948cd539a8d981c1836040516116609190614b7b565b6001600160a01b038116600090815260fd60205260408120819081906120e59086906133fb565b915091508161210c576001600160a01b038416600090815260cb602052604090205461210e565b805b95945050505050565b6000805160206157da83398151915261212f81612e2a565b6103cb61213c83826153e0565b508160405161214b919061549f565b60405180910390207f1bcb2cc6a051bf8e937bfdae2d991a1b11f4e750bbdcb3495bc36d7c7ab5f161836040516116609190614b7b565b6000805160206157da83398151915261219a81612e2a565b6103cf6121a783826153e0565b50816040516121b6919061549f565b60405180910390207fcded00ba32686bbb699d11c9bf229b4c3e09b92803feb334ccef85538c38ca3c836040516116609190614b7b565b600060008051602061581a83398151915261220781612e2a565b61197e8484613450565b600061221c81612e2a565b6101cd61222983826153e0565b5081604051612238919061549f565b60405180910390207ffc577d5a6019d7ff3e419405cfa719f653cfe7680f822b2b0b4179eb10a2c269836040516116609190614b7b565b606060ff82166122a357505060408051808201909152600e81526d2737903932b9ba3934b1ba34b7b760911b602082015290565b60001960ff8316016122df575050604080518082019091526014815273105b1b081d1c985b9cd9995c9cc81c185d5cd95960621b602082015290565b60011960ff83160161231c5750506040805180820190915260158152742a34329030b2323932b9b99034b990333937bd32b760591b602082015290565b6033546001600160a01b03161561233657610ad9826134f8565b919050565b6000805160206157fa83398151915261235381612e2a565b6118e68261356c565b60008051602061579a83398151915261237481612e2a565b611957613673565b6000918252610167602090815260408084206001600160a01b0393909316845291905290205460ff1690565b606060cf8054610aee90615358565b6000805160206157fa8339815191526123cf81612e2a565b6118e6826136b1565b6000806123e3612cfc565b905060006123f18286612824565b9050838110156124515760405162461bcd60e51b815260206004820152602560248201527f45524332303a2064656372656173656420616c6c6f77616e63652062656c6f77604482015264207a65726f60d81b60648201526084016118d3565b611a9c8286868403612d06565b600061246981612e2a565b603380546001600160a01b0319166001600160a01b0384169081179091556040517f9c4d5c11b88d1e3d9c7ad50900cb6d10ac72853248cdc85ca868fb772e62b44990600090a25050565b6000806124bf612cfc565b9050610b898185856137d1565b6060610102805480602002602001604051908101604052809291908181526020018280548015610b6757602002820191906000526020600020905b815481526020019060010190808311612507575050505050905090565b6033546000906001600160a01b031615610b8957612543848484613989565b90506115ee565b6000805160206157da83398151915261256281612e2a565b6103ca61256f83826153e0565b508160405161257e919061549f565b60405180910390207f8455f5046de4a823b3559671d389aa0642c7e96db280bf12ece34ed6dbfc9d9b836040516116609190614b7b565b6000805160206157da8339815191526125cd81612e2a565b6103c682905560405182907f5e2a471fe68796ada631b0f19c39a3d5665c59832c0e059f03e5c3fa3a86bbc290600090a25050565b6000805160206157fa83398151915261261a81612e2a565b61183e8383613a07565b600061262f81612e2a565b6101cf82905560405182907fcb8d44cf5fbf57e33cf3ba3a7fd189f805e29a0093d8e0c85b9bf7ac8403837490600090a25050565b600061267260665460ff1690565b1561267e576001612543565b6001600160a01b03841660009081526098602052604090205460ff16156126a6576002612543565b6033546001600160a01b0316156126c257612543848484613c69565b60006115eb565b6101cd805461155d90615358565b600082815261016760205260409020600101546126f381612e2a565b61183e8383612f39565b600061270881612e2a565b6101ce61271583826153e0565b5081604051612724919061549f565b60405180910390207f935ca7f5c06e3f1956aa394969531b268ad8a01de033d485cdabd79ffef3ba13836040516116609190614b7b565b6000805160206157da83398151915261277381612e2a565b6103cd61278083826153e0565b508160405161278f919061549f565b60405180910390207f8528a756683d9ff1c2f830fdf4673cf4da5e5d3451715d83a2b29835b419ce30836040516116609190614b7b565b60006127d181612e2a565b6101cc6127de83826153e0565b50816040516127ed919061549f565b60405180910390207f615dae5ba8f512acb28e05c78f1fae681dadf61e242fac2cfcbc117e0d451e3e836040516116609190614b7b565b6001600160a01b03918216600090815260cc6020908152604080832093909416825291909152205490565b60008051602061575a83398151915261286781612e2a565b6128718383613ce7565b826001600160a01b03167fcc16f5dbb4873280815c1ee09dbd06736cffcc184412cf7a71a0fdb75d397ca5836040516119e391815260200190565b60008051602061577a8339815191526128c481612e2a565b6040805160608101825285151580825285151560208301819052928201859052610403805461010090940261ff001990921661ffff19909416939093171782559061040461291285826153e0565b505060405185151591507fe241461ce7474b6fe1c3f8aaa4150fc7545522186efe4ca13ff14ea90db3120090600090a2604051831515907f542f36cc291fb3c7480ccc6fe5355dc6f63d22767c8df4020b547c6536c3795c90600090a28160405161297d919061549f565b60405180910390207f3050dc30d1115cd7dc7dadd07203d3151a941499e2c1609526139e2adfb43162836040516129b49190614b7b565b60405180910390a250505050565b600054610100900460ff16158080156129e25750600054600160ff909116105b806129fc5750303b1580156129fc575060005460ff166001145b612a5f5760405162461bcd60e51b815260206004820152602e60248201527f496e697469616c697a61626c653a20636f6e747261637420697320616c72656160448201526d191e481a5b9a5d1a585b1a5e995960921b60648201526084016118d3565b6000805460ff191660011790558015612a82576000805461ff0019166101001790555b612a938a8a8a8a8a8a8a8a8a613e27565b8015612ad9576000805461ff0019169055604051600181527f7f26b83ff96e1f2b6a682f133852f6798a09c465da95921460cefb38474024989060200160405180910390a15b50505050505050505050565b6101ce805461155d90615358565b6000805160206157fa833981519152612b0b81612e2a565b6118e682613f04565b60408051600081526020810190915261010254606091901561233657600080612b3b61404f565b91509150816000148015612b50575061010054155b15612baf57610102805480602002602001604051908101604052809291908181526020018280548015612ba257602002820191906000526020600020905b815481526020019060010190808311612b8e575b5050505050935050505090565b61010254612bbe8260016154d1565b14612c985761010254600090600190612bd89084906154e4565b612be291906154e4565b9050806001600160401b03811115612bfc57612bfc614cc5565b604051908082528060200260200182016040528015612c25578160200160208202803683370190505b50935060005b8451811015612c955761010281612c438560016154d1565b612c4d91906154d1565b81548110612c5d57612c5d6154f7565b9060005260206000200154858281518110612c7a57612c7a6154f7565b6020908102919091010152612c8e8161550d565b9050612c2b565b50505b5050919050565b6001600160a01b03163b151590565b60006118525b60007f00000000000000000000000000000000000000000000000000000000000000006001600160a01b03163303612cf3575060131936013560601c90565b503390565b3390565b6000611852612cae565b6001600160a01b038316612d685760405162461bcd60e51b8152602060048201526024808201527f45524332303a20617070726f76652066726f6d20746865207a65726f206164646044820152637265737360e01b60648201526084016118d3565b6001600160a01b038216612dc95760405162461bcd60e51b815260206004820152602260248201527f45524332303a20617070726f766520746f20746865207a65726f206164647265604482015261737360f01b60648201526084016118d3565b6001600160a01b03838116600081815260cc602090815260408083209487168084529482529182902085905590518481527f8c5be1e5ebec7d5bd14f71427d1e84f3dd0314c0f7b2291e5b200ac8c7c3b925910160405180910390a3505050565b61195781612e36612cfc565b61410d565b600080612e49858585614166565b90508015156001036115eb57612e5d612cfc565b6001600160a01b0316856001600160a01b03167f7c2b9369bf4a6bd9745889c658ad00a4d57e280c4c80fa1c74db2a9e52c1363585604051612ea191815260200190565b60405180910390a3949350505050565b612ebb828261237c565b6118e6576000828152610167602090815260408083206001600160a01b03851684529091529020805460ff19166001179055612ef5612cfc565b6001600160a01b0316816001600160a01b0316837f2f8788117e7eff1d82e926ec794901d17c78024a50270940304540a733656f0d60405160405180910390a45050565b612f43828261237c565b156118e6576000828152610167602090815260408083206001600160a01b03851684529091529020805460ff19169055612f7b612cfc565b6001600160a01b0316816001600160a01b0316837ff6391f5c32d9c69d2a47ea670b442974b53935d1edc7fd64eb21e047a839171b60405160405180910390a45050565b428111612fde5760405162461bcd60e51b81526004016118d390615526565b600080612fea83614189565b91509150811561303c5760405162461bcd60e51b815260206004820152601760248201527f536e617073686f7420616c72656164792065786973747300000000000000000060448201526064016118d3565b6101025481036130815761010280546001810182556000919091527f93bdaa6a4190909b7c3fbe8d42169ffe1cab19f51dfc8db24c71abf849eced4a01839055613157565b61010280548190613094906001906154e4565b815481106130a4576130a46154f7565b6000918252602080832090910154835460018101855593835290822090920191909155610102546130d7906002906154e4565b90505b81811115613134576101026130f06001836154e4565b81548110613100576131006154f7565b9060005260206000200154610102828154811061311f5761311f6154f7565b600091825260209091200155600019016130da565b5082610102828154811061314a5761314a6154f7565b6000918252602090912001555b60405183906000907fe2ad3b1abe53383dbe6359f02f11ae76d91cfab321b37083b16e1d96a81d4183908290a3505050565b613191614201565b6066805460ff191690557f5db9ee0a495bf2e6ff9c91a7834c1ba4fdd244a5e8aa4e537bd38aeae4b073aa6131c4612cfc565b6040516001600160a01b03909116815260200160405180910390a1565b6001600160a01b03821660009081526098602052604081205460ff161561320a57506000610ad9565b6001600160a01b03831660009081526098602052604090819020805460ff191660011790555161323b90839061549f565b6040518091039020836001600160a01b0316613255612cfc565b6001600160a01b03167fe80aede59db0b770aef5e4bd04670759d38e64959d07a4343257a0a4f6b6d1ed8560405161328d9190614b7b565b60405180910390a450600192915050565b6001600160a01b0382166132f45760405162461bcd60e51b815260206004820152601f60248201527f45524332303a206d696e7420746f20746865207a65726f20616464726573730060448201526064016118d3565b6133006000838361424a565b8060cd600082825461331291906154d1565b90915550506001600160a01b038216600081815260cb60209081526040808320805486019055518481527fddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef910160405180910390a35050565b6001600160a01b037f00000000000000000000000000000000000000000000000000000000000000001630036133f95760405162461bcd60e51b815260206004820152602d60248201527f4469726563742063616c6c20746f2074686520696d706c656d656e746174696f60448201526c1b881b9bdd08185b1b1bddd959609a1b60648201526084016118d3565b565b600080806134098486614394565b84549091508103613421576000809250925050613449565b6001846001018281548110613438576134386154f7565b906000526020600020015492509250505b9250929050565b6001600160a01b03821660009081526098602052604081205460ff1661347857506000610ad9565b6001600160a01b03831660009081526098602052604090819020805460ff19169055516134a690839061549f565b6040518091039020836001600160a01b03166134c0612cfc565b6001600160a01b03167f7a52fdbc4f3e9f93670cd35b5b9c2d974791d25c5c04984336a80be3f7f42c328560405161328d9190614b7b565b603354604051637f4ab1dd60e01b815260ff831660048201526060916001600160a01b031690637f4ab1dd90602401600060405180830381865afa158015613544573d6000803e3d6000fd5b505050506040513d6000823e601f3d908101601f19168201604052610ad9919081019061555d565b42811161358b5760405162461bcd60e51b81526004016118d3906155ca565b60008061359783614189565b91509150816135dd5760405162461bcd60e51b815260206004820152601260248201527114db985c1cda1bdd081b9bdd08199bdd5b9960721b60448201526064016118d3565b805b610102546135ee8260016154d1565b1015613645576101026136028260016154d1565b81548110613612576136126154f7565b90600052602060002001546101028281548110613631576136316154f7565b6000918252602090912001556001016135df565b50610102805480613658576136586155f9565b60019003818190600052602060002001600090559055505050565b61367b614435565b6066805460ff191660011790557f62e78cea01bee320cd4e420270b5ea74000d11b0c9f74754ebdbfc544b05a2586131c4612cfc565b4281116136d05760405162461bcd60e51b81526004016118d390615526565b610102541561376e5761010280546136ea906001906154e4565b815481106136fa576136fa6154f7565b9060005260206000200154811161376e5760405162461bcd60e51b815260206004820152603260248201527f74696d652068617320746f2062652067726561746572207468616e20746865206044820152716c61737420736e617073686f742074696d6560701b60648201526084016118d3565b610102805460018101825560009182527f93bdaa6a4190909b7c3fbe8d42169ffe1cab19f51dfc8db24c71abf849eced4a018290556040518291907fe2ad3b1abe53383dbe6359f02f11ae76d91cfab321b37083b16e1d96a81d4183908290a350565b6001600160a01b0383166138355760405162461bcd60e51b815260206004820152602560248201527f45524332303a207472616e736665722066726f6d20746865207a65726f206164604482015264647265737360d81b60648201526084016118d3565b6001600160a01b0382166138975760405162461bcd60e51b815260206004820152602360248201527f45524332303a207472616e7366657220746f20746865207a65726f206164647260448201526265737360e81b60648201526084016118d3565b6138a283838361424a565b6001600160a01b038316600090815260cb60205260409020548181101561391a5760405162461bcd60e51b815260206004820152602660248201527f45524332303a207472616e7366657220616d6f756e7420657863656564732062604482015265616c616e636560d01b60648201526084016118d3565b6001600160a01b03808516600081815260cb602052604080822086860390559286168082529083902080548601905591517fddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef9061397a9086815260200190565b60405180910390a35b50505050565b60335460405163634a350960e11b81526001600160a01b038581166004830152848116602483015260448201849052600092169063c6946a1290606401602060405180830381865afa1580156139e3573d6000803e3d6000fd5b505050506040513d601f19601f820116820180604052508101906115eb919061560f565b428211613a265760405162461bcd60e51b81526004016118d3906155ca565b428111613a455760405162461bcd60e51b81526004016118d390615526565b61010254613a8d5760405162461bcd60e51b81526020600482015260156024820152741b9bc81cd8da19591d5b1959081cdb985c1cda1bdd605a1b60448201526064016118d3565b600080613a9984614189565b9150915081613adf5760405162461bcd60e51b815260206004820152601260248201527114db985c1cda1bdd081b9bdd08199bdd5b9960721b60448201526064016118d3565b61010254613aee8260016154d1565b1015613b7e57610102613b028260016154d1565b81548110613b1257613b126154f7565b90600052602060002001548310613b7e5760405162461bcd60e51b815260206004820152602a60248201527f74696d652068617320746f206265206c657373207468616e20746865206e65786044820152691d081cdb985c1cda1bdd60b21b60648201526084016118d3565b8015613c1557610102613b926001836154e4565b81548110613ba257613ba26154f7565b90600052602060002001548311613c155760405162461bcd60e51b815260206004820152603160248201527f74696d652068617320746f2062652067726561746572207468616e20746865206044820152701c1c995d9a5bdd5cc81cdb985c1cda1bdd607a1b60648201526084016118d3565b826101028281548110613c2a57613c2a6154f7565b6000918252602082200191909155604051849186917fe2ad3b1abe53383dbe6359f02f11ae76d91cfab321b37083b16e1d96a81d41839190a350505050565b60335460405163d4ce141560e01b81526001600160a01b038581166004830152848116602483015260448201849052600092169063d4ce141590606401602060405180830381865afa158015613cc3573d6000803e3d6000fd5b505050506040513d601f19601f820116820180604052508101906115eb919061562c565b6001600160a01b038216613d475760405162461bcd60e51b815260206004820152602160248201527f45524332303a206275726e2066726f6d20746865207a65726f206164647265736044820152607360f81b60648201526084016118d3565b613d538260008361424a565b6001600160a01b038216600090815260cb602052604090205481811015613dc75760405162461bcd60e51b815260206004820152602260248201527f45524332303a206275726e20616d6f756e7420657863656564732062616c616e604482015261636560f01b60648201526084016118d3565b6001600160a01b038316600081815260cb60209081526040808320868603905560cd80548790039055518581529192917fddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef910160405180910390a3505050565b600054610100900460ff16613e4e5760405162461bcd60e51b81526004016118d390615649565b613e5661447b565b613e6087876144a2565b613e6861447b565b613e7061447b565b613e786144e2565b613e8061447b565b613e88614515565b613e918361454a565b613e9a886145ca565b613ea261447b565b613eaa61447b565b613eb261447b565b613ebc6000614605565b613ec461447b565b613ecc61447b565b613ed461447b565b613edc61447b565b613ee461447b565b613ef085858484614643565b613ef98961469d565b505050505050505050565b428111613f235760405162461bcd60e51b81526004016118d3906155ca565b61010254613f6b5760405162461bcd60e51b8152602060048201526015602482015274139bc81cdb985c1cda1bdd081cd8da19591d5b1959605a1b60448201526064016118d3565b6101028054613f7c906001906154e4565b81548110613f8c57613f8c6154f7565b90600052602060002001548114613ff75760405162461bcd60e51b815260206004820152602960248201527f4f6e6c7920746865206c61737420736e617073686f742063616e20626520756e6044820152681cd8da19591d5b195960ba1b60648201526084016118d3565b610102805480614009576140096155f9565b60019003818190600052602060002001600090559055807f06e2498f5548e5491bfe985562cc494131eae56b5b6543b59129c8886f129f6560405160405180910390a250565b61010254600090819080158061407d57508061010154600161407191906154d1565b14801561407d57508215155b1561408c576000939092509050565b600081925060006101015490505b82811015614105574261010282815481106140b7576140b76154f7565b9060005260206000200154116140f05761010281815481106140db576140db6154f7565b906000526020600020015491508093506140f5565b614105565b6140fe8161550d565b905061409a565b509391925050565b614117828261237c565b6118e657614124816146d8565b61412f8360206146ea565b604051602001614140929190615694565b60408051601f198184030181529082905262461bcd60e51b82526118d391600401614b7b565b600080614171612cfc565b905061417e858285614885565b611a9c8585856137d1565b6000808061419961010285614394565b6101025490915081148015906141cc57508361010282815481106141bf576141bf6154f7565b9060005260206000200154145b156141dc57600194909350915050565b6101025481146141f157600094909350915050565b5050610102546000939092509050565b60665460ff166133f95760405162461bcd60e51b815260206004820152601460248201527314185d5cd8589b194e881b9bdd081c185d5cd95960621b60448201526064016118d3565b60665460ff16156142a85760405162461bcd60e51b815260206004820152602260248201527f434d5441543a20746f6b656e207472616e73666572207768696c652070617573604482015261195960f21b60648201526084016118d3565b6001600160a01b03831660009081526098602052604090205460ff161561431c5760405162461bcd60e51b815260206004820152602260248201527f434d5441543a20746f6b656e207472616e73666572207768696c652066726f7a60448201526132b760f11b60648201526084016118d3565b6143278383836148f9565b614332838383612524565b61183e5760405162461bcd60e51b815260206004820152602d60248201527f434d5441543a207472616e736665722072656a65637465642062792076616c6960448201526c646174696f6e206d6f64756c6560981b60648201526084016118d3565b815460009081036143a757506000610ad9565b82546000905b808210156143f15760006143c18383614942565b9050846143ce878361495d565b5411156143dd578091506143eb565b6143e88160016154d1565b92505b506143ad565b6000821180156144145750836144118661440c6001866154e4565b61495d565b54145b1561442d576144246001836154e4565b92505050610ad9565b509050610ad9565b60665460ff16156133f95760405162461bcd60e51b815260206004820152601060248201526f14185d5cd8589b194e881c185d5cd95960821b60448201526064016118d3565b600054610100900460ff166133f95760405162461bcd60e51b81526004016118d390615649565b600054610100900460ff166144c95760405162461bcd60e51b81526004016118d390615649565b60ce6144d583826153e0565b5060cf61183e82826153e0565b600054610100900460ff166145095760405162461bcd60e51b81526004016118d390615649565b6066805460ff19169055565b600054610100900460ff1661453c5760405162461bcd60e51b81526004016118d390615649565b600061010081905561010155565b600054610100900460ff166145715760405162461bcd60e51b81526004016118d390615649565b6001600160a01b0381161561195757603380546001600160a01b0319166001600160a01b0383169081179091556040517f9c4d5c11b88d1e3d9c7ad50900cb6d10ac72853248cdc85ca868fb772e62b44990600090a250565b600054610100900460ff166145f15760405162461bcd60e51b81526004016118d390615649565b6145fc600082612eb1565b6119578161496e565b600054610100900460ff1661462c5760405162461bcd60e51b81526004016118d390615649565b610392805460ff191660ff92909216919091179055565b600054610100900460ff1661466a5760405162461bcd60e51b81526004016118d390615649565b6101cc61467785826153e0565b506101cd61468584826153e0565b506101ce61469383826153e0565b506101cf55505050565b600054610100900460ff166146c45760405162461bcd60e51b81526004016118d390615649565b6101cb805460ff1916911515919091179055565b6060610ad96001600160a01b03831660145b606060006146f9836002615709565b6147049060026154d1565b6001600160401b0381111561471b5761471b614cc5565b6040519080825280601f01601f191660200182016040528015614745576020820181803683370190505b509050600360fc1b81600081518110614760576147606154f7565b60200101906001600160f81b031916908160001a905350600f60fb1b8160018151811061478f5761478f6154f7565b60200101906001600160f81b031916908160001a90535060006147b3846002615709565b6147be9060016154d1565b90505b6001811115614836576f181899199a1a9b1b9c1cb0b131b232b360811b85600f16601081106147f2576147f26154f7565b1a60f81b828281518110614808576148086154f7565b60200101906001600160f81b031916908160001a90535060049490941c9361482f81615720565b90506147c1565b5083156115ee5760405162461bcd60e51b815260206004820181905260248201527f537472696e67733a20686578206c656e67746820696e73756666696369656e7460448201526064016118d3565b60006148918484612824565b9050600019811461398357818110156148ec5760405162461bcd60e51b815260206004820152601d60248201527f45524332303a20696e73756666696369656e7420616c6c6f77616e636500000060448201526064016118d3565b6139838484848403612d06565b614901614a16565b6001600160a01b038316156149395761491983614a39565b6001600160a01b038216156149315761183e82614a39565b61183e614a6c565b61493182614a39565b60006149516002848418615737565b6115ee908484166154d1565b60008281526020812082018061197e565b61498660008051602061581a83398151915282612eb1565b61499e6000805160206157ba83398151915282612eb1565b6149b660008051602061575a83398151915282612eb1565b6149ce60008051602061579a83398151915282612eb1565b6149e66000805160206157fa83398151915282612eb1565b6149fe6000805160206157da83398151915282612eb1565b61195760008051602061577a83398151915282612eb1565b600080614a2161404f565b909250905081156118e6576101009190915561010155565b6001600160a01b038116600090815260fd6020908152604080832060cb909252909120546119579190614a7a565b614a7a565b6133f960fe614a6760cd5490565b6101005480614a8884614abc565b101561183e578254600180820185556000858152602080822090930193909355938401805494850181558252902090910155565b80546000908103614acf57506000919050565b81548290614adf906001906154e4565b81548110614aef57614aef6154f7565b90600052602060002001549050919050565b600060208284031215614b1357600080fd5b81356001600160e01b0319811681146115ee57600080fd5b60005b83811015614b46578181015183820152602001614b2e565b50506000910152565b60008151808452614b67816020860160208601614b2b565b601f01601f19169290920160200192915050565b6020815260006115ee6020830184614b4f565b6001600160a01b038116811461195757600080fd5b803561233681614b8e565b60008060408385031215614bc157600080fd5b8235614bcc81614b8e565b946020939093013593505050565b60006101808e83528d6020840152806040840152614bfa8184018e614b4f565b90508281036060840152614c0e818d614b4f565b90508281036080840152614c22818c614b4f565b905082810360a0840152614c36818b614b4f565b905082810360c0840152614c4a818a614b4f565b905082810360e0840152614c5e8189614b4f565b9050828103610100840152614c738188614b4f565b9050828103610120840152614c888187614b4f565b9050828103610140840152614c9d8186614b4f565b9050828103610160840152614cb28185614b4f565b9f9e505050505050505050505050505050565b634e487b7160e01b600052604160045260246000fd5b604051601f8201601f191681016001600160401b0381118282101715614d0357614d03614cc5565b604052919050565b60006001600160401b03821115614d2457614d24614cc5565b50601f01601f191660200190565b600082601f830112614d4357600080fd5b8135614d56614d5182614d0b565b614cdb565b818152846020838601011115614d6b57600080fd5b816020850160208301376000918101602001919091529392505050565b6000806000806000806000806000806000806101808d8f031215614dab57600080fd5b8c359b5060208d01359a506001600160401b0360408e01351115614dce57600080fd5b614dde8e60408f01358f01614d32565b99506001600160401b0360608e01351115614df857600080fd5b614e088e60608f01358f01614d32565b98506001600160401b0360808e01351115614e2257600080fd5b614e328e60808f01358f01614d32565b97506001600160401b0360a08e01351115614e4c57600080fd5b614e5c8e60a08f01358f01614d32565b96506001600160401b0360c08e01351115614e7657600080fd5b614e868e60c08f01358f01614d32565b95506001600160401b0360e08e01351115614ea057600080fd5b614eb08e60e08f01358f01614d32565b94506001600160401b036101008e01351115614ecb57600080fd5b614edc8e6101008f01358f01614d32565b93506001600160401b036101208e01351115614ef757600080fd5b614f088e6101208f01358f01614d32565b92506001600160401b036101408e01351115614f2357600080fd5b614f348e6101408f01358f01614d32565b91506001600160401b036101608e01351115614f4f57600080fd5b614f608e6101608f01358f01614d32565b90509295989b509295989b509295989b565b600080600060608486031215614f8757600080fd5b8335614f9281614b8e565b92506020840135614fa281614b8e565b929592945050506040919091013590565b600060208284031215614fc557600080fd5b81356001600160401b03811115614fdb57600080fd5b61197e84828501614d32565b600060208284031215614ff957600080fd5b5035919050565b6000806040838503121561501357600080fd5b82359150602083013561502581614b8e565b809150509250929050565b6000806040838503121561504357600080fd5b823561504e81614b8e565b915060208301356001600160401b0381111561506957600080fd5b61507585828601614d32565b9150509250929050565b60008060006060848603121561509457600080fd5b833561509f81614b8e565b95602085013595506040909401359392505050565b801515811461195757600080fd5b8035612336816150b4565b6000602082840312156150df57600080fd5b81356115ee816150b4565b8315158152821515602082015260606040820152600061210e6060830184614b4f565b60006020828403121561511f57600080fd5b81356115ee81614b8e565b60ff8116811461195757600080fd5b60006020828403121561514b57600080fd5b81356115ee8161512a565b6020808252825182820181905260009190848201906040850190845b8181101561518e57835183529284019291840191600101615172565b50909695505050505050565b600080604083850312156151ad57600080fd5b50508035926020909101359150565b600080604083850312156151cf57600080fd5b82356151da81614b8e565b9150602083013561502581614b8e565b6000806000606084860312156151ff57600080fd5b833561520a816150b4565b9250602084013561521a816150b4565b915060408401356001600160401b0381111561523557600080fd5b61524186828701614d32565b9150509250925092565b60008060008060008060008060006101208a8c03121561526a57600080fd5b6152738a6150c2565b985061528160208b01614ba3565b975060408a01356001600160401b038082111561529d57600080fd5b6152a98d838e01614d32565b985060608c01359150808211156152bf57600080fd5b6152cb8d838e01614d32565b975060808c01359150808211156152e157600080fd5b6152ed8d838e01614d32565b965060a08c013591508082111561530357600080fd5b61530f8d838e01614d32565b955061531d60c08d01614ba3565b945060e08c013591508082111561533357600080fd5b506153408c828d01614d32565b9250506101008a013590509295985092959850929598565b600181811c9082168061536c57607f821691505b60208210810361538c57634e487b7160e01b600052602260045260246000fd5b50919050565b601f82111561183e57600081815260208120601f850160051c810160208610156153b95750805b601f850160051c820191505b818110156153d8578281556001016153c5565b505050505050565b81516001600160401b038111156153f9576153f9614cc5565b61540d816154078454615358565b84615392565b602080601f831160018114615442576000841561542a5750858301515b600019600386901b1c1916600185901b1785556153d8565b600085815260208120601f198616915b8281101561547157888601518255948401946001909101908401615452565b508582101561548f5787850151600019600388901b60f8161c191681555b5050505050600190811b01905550565b600082516154b1818460208701614b2b565b9190910192915050565b634e487b7160e01b600052601160045260246000fd5b80820180821115610ad957610ad96154bb565b81810381811115610ad957610ad96154bb565b634e487b7160e01b600052603260045260246000fd5b60006001820161551f5761551f6154bb565b5060010190565b6020808252601e908201527f536e617073686f74207363686564756c656420696e2074686520706173740000604082015260600190565b60006020828403121561556f57600080fd5b81516001600160401b0381111561558557600080fd5b8201601f8101841361559657600080fd5b80516155a4614d5182614d0b565b8181528560208385010111156155b957600080fd5b61210e826020830160208601614b2b565b602080825260159082015274536e617073686f7420616c726561647920646f6e6560581b604082015260600190565b634e487b7160e01b600052603160045260246000fd5b60006020828403121561562157600080fd5b81516115ee816150b4565b60006020828403121561563e57600080fd5b81516115ee8161512a565b6020808252602b908201527f496e697469616c697a61626c653a20636f6e7472616374206973206e6f74206960408201526a6e697469616c697a696e6760a81b606082015260800190565b7f416363657373436f6e74726f6c3a206163636f756e74200000000000000000008152600083516156cc816017850160208801614b2b565b7001034b99036b4b9b9b4b733903937b6329607d1b60179184019182015283516156fd816028840160208801614b2b565b01602801949350505050565b8082028115828204841417610ad957610ad96154bb565b60008161572f5761572f6154bb565b506000190190565b60008261575457634e487b7160e01b600052601260045260246000fd5b50049056fe3c11d16cbaffd01df69ce1c404f6340ee057498f5f00246190ea54220576a848aa2de0737115053bf7d3d68e733306557628aef4b4aefa746cbf344fc726724765d7a28e3265b37a6474929f336521b332c1681b933f6cb9f3376673440d862a9f2df0fed2c77648de5860a4cc508cd0818c85b8b8a1ab4ceeef8d981c8956a6c6f3350ab30f55ce45863160fc345c1663d4633fe7cacfd3b9bbb6420a9147f8809a0fc49fc0600540f1d39e23454e1f6f215bc7505fa22b17c154616570ddef973ef39d76cc2c6090feab1c030bec6ab5db557f64df047a4c4f9b5953cf1df3a2646970667358221220d69dfe59faea3b719d827a25076210beccf646f567c65fabac58f8ed4f5b5dda64736f6c63430008110033496e697469616c697a61626c653a20636f6e7472616374206973206e6f7420697f26b83ff96e1f2b6a682f133852f6798a09c465da95921460cefb3847402498"
         self.abi = [
	            {
                    "inputs": [
                        {
                            "internalType": "address",
                            "name": "forwarderIrrevocable",
                            "type": "address"
                        },
                        {
                            "internalType": "bool",
                            "name": "deployedWithProxyIrrevocable_",
                            "type": "bool"
                        },
                        {
                            "internalType": "address",
                            "name": "admin",
                            "type": "address"
                        },
                        {
                            "internalType": "string",
                            "name": "nameIrrevocable",
                            "type": "string"
                        },
                        {
                            "internalType": "string",
                            "name": "symbolIrrevocable",
                            "type": "string"
                        },
                        {
                            "internalType": "string",
                            "name": "tokenId",
                            "type": "string"
                        },
                        {
                            "internalType": "string",
                            "name": "terms",
                            "type": "string"
                        },
                        {
                            "internalType": "contract IRuleEngine",
                            "name": "ruleEngine",
                            "type": "address"
                        },
                        {
                            "internalType": "string",
                            "name": "information",
                            "type": "string"
                        },
                        {
                            "internalType": "uint256",
                            "name": "flag",
                            "type": "uint256"
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
                            "internalType": "string",
                            "name": "newBondHolderIndexed",
                            "type": "string"
                        },
                        {
                            "indexed": False,
                            "internalType": "string",
                            "name": "newBondHolder",
                            "type": "string"
                        }
                    ],
                    "name": "BondHolderSet",
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
                            "indexed": False,
                            "internalType": "uint256",
                            "name": "amount",
                            "type": "uint256"
                        }
                    ],
                    "name": "Burn",
                    "type": "event"
                },
                {
                    "anonymous": False,
                    "inputs": [
                        {
                            "indexed": True,
                            "internalType": "string",
                            "name": "newBusinessDayConventionIndexed",
                            "type": "string"
                        },
                        {
                            "indexed": False,
                            "internalType": "string",
                            "name": "newBusinessDayConvention",
                            "type": "string"
                        }
                    ],
                    "name": "BusinessDayConventionSet",
                    "type": "event"
                },
                {
                    "anonymous": False,
                    "inputs": [
                        {
                            "indexed": True,
                            "internalType": "string",
                            "name": "newCouponFrequencyIndexed",
                            "type": "string"
                        },
                        {
                            "indexed": False,
                            "internalType": "string",
                            "name": "newCouponFrequency",
                            "type": "string"
                        }
                    ],
                    "name": "CouponFrequencySet",
                    "type": "event"
                },
                {
                    "anonymous": False,
                    "inputs": [
                        {
                            "indexed": True,
                            "internalType": "string",
                            "name": "newDayCountConventionIndexed",
                            "type": "string"
                        },
                        {
                            "indexed": False,
                            "internalType": "string",
                            "name": "newDayCountConvention",
                            "type": "string"
                        }
                    ],
                    "name": "DayCountConventionSet",
                    "type": "event"
                },
                {
                    "anonymous": False,
                    "inputs": [
                        {
                            "indexed": True,
                            "internalType": "bool",
                            "name": "newFlagDefault",
                            "type": "bool"
                        }
                    ],
                    "name": "FlagDefaultSet",
                    "type": "event"
                },
                {
                    "anonymous": False,
                    "inputs": [
                        {
                            "indexed": True,
                            "internalType": "bool",
                            "name": "newFlagRedeemed",
                            "type": "bool"
                        }
                    ],
                    "name": "FlagRedeemedSet",
                    "type": "event"
                },
                {
                    "anonymous": False,
                    "inputs": [
                        {
                            "indexed": True,
                            "internalType": "uint256",
                            "name": "newFlag",
                            "type": "uint256"
                        }
                    ],
                    "name": "FlagSet",
                    "type": "event"
                },
                {
                    "anonymous": False,
                    "inputs": [
                        {
                            "indexed": True,
                            "internalType": "address",
                            "name": "enforcer",
                            "type": "address"
                        },
                        {
                            "indexed": True,
                            "internalType": "address",
                            "name": "owner",
                            "type": "address"
                        },
                        {
                            "indexed": True,
                            "internalType": "string",
                            "name": "reasonIndexed",
                            "type": "string"
                        },
                        {
                            "indexed": False,
                            "internalType": "string",
                            "name": "reason",
                            "type": "string"
                        }
                    ],
                    "name": "Freeze",
                    "type": "event"
                },
                {
                    "anonymous": False,
                    "inputs": [
                        {
                            "indexed": True,
                            "internalType": "string",
                            "name": "newGuarantorIndexed",
                            "type": "string"
                        },
                        {
                            "indexed": False,
                            "internalType": "string",
                            "name": "newGuarantor",
                            "type": "string"
                        }
                    ],
                    "name": "GuarantorSet",
                    "type": "event"
                },
                {
                    "anonymous": False,
                    "inputs": [
                        {
                            "indexed": True,
                            "internalType": "string",
                            "name": "newInformationIndexed",
                            "type": "string"
                        },
                        {
                            "indexed": False,
                            "internalType": "string",
                            "name": "newInformation",
                            "type": "string"
                        }
                    ],
                    "name": "InformationSet",
                    "type": "event"
                },
                {
                    "anonymous": False,
                    "inputs": [
                        {
                            "indexed": False,
                            "internalType": "uint8",
                            "name": "version",
                            "type": "uint8"
                        }
                    ],
                    "name": "Initialized",
                    "type": "event"
                },
                {
                    "anonymous": False,
                    "inputs": [
                        {
                            "indexed": True,
                            "internalType": "string",
                            "name": "newInterestPaymentDateIndexed",
                            "type": "string"
                        },
                        {
                            "indexed": False,
                            "internalType": "string",
                            "name": "newInterestPaymentDate",
                            "type": "string"
                        }
                    ],
                    "name": "InterestPaymentDateSet",
                    "type": "event"
                },
                {
                    "anonymous": False,
                    "inputs": [
                        {
                            "indexed": True,
                            "internalType": "uint256",
                            "name": "newInterestRate",
                            "type": "uint256"
                        }
                    ],
                    "name": "InterestRateSet",
                    "type": "event"
                },
                {
                    "anonymous": False,
                    "inputs": [
                        {
                            "indexed": True,
                            "internalType": "string",
                            "name": "newInterestScheduleFormatIndexed",
                            "type": "string"
                        },
                        {
                            "indexed": False,
                            "internalType": "string",
                            "name": "newInterestScheduleFormat",
                            "type": "string"
                        }
                    ],
                    "name": "InterestScheduleFormatSet",
                    "type": "event"
                },
                {
                    "anonymous": False,
                    "inputs": [
                        {
                            "indexed": True,
                            "internalType": "string",
                            "name": "newIssuanceDateIndexed",
                            "type": "string"
                        },
                        {
                            "indexed": False,
                            "internalType": "string",
                            "name": "newIssuanceDate",
                            "type": "string"
                        }
                    ],
                    "name": "IssuanceDateSet",
                    "type": "event"
                },
                {
                    "anonymous": False,
                    "inputs": [
                        {
                            "indexed": True,
                            "internalType": "string",
                            "name": "newMaturityDateIndexed",
                            "type": "string"
                        },
                        {
                            "indexed": False,
                            "internalType": "string",
                            "name": "newMaturityDate",
                            "type": "string"
                        }
                    ],
                    "name": "MaturityDateSet",
                    "type": "event"
                },
                {
                    "anonymous": False,
                    "inputs": [
                        {
                            "indexed": True,
                            "internalType": "address",
                            "name": "beneficiary",
                            "type": "address"
                        },
                        {
                            "indexed": False,
                            "internalType": "uint256",
                            "name": "amount",
                            "type": "uint256"
                        }
                    ],
                    "name": "Mint",
                    "type": "event"
                },
                {
                    "anonymous": False,
                    "inputs": [
                        {
                            "indexed": True,
                            "internalType": "uint256",
                            "name": "newParValue",
                            "type": "uint256"
                        }
                    ],
                    "name": "ParValueSet",
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
                            "internalType": "string",
                            "name": "newPublicHolidaysCalendarIndexed",
                            "type": "string"
                        },
                        {
                            "indexed": False,
                            "internalType": "string",
                            "name": "newPublicHolidaysCalendar",
                            "type": "string"
                        }
                    ],
                    "name": "PublicHolidaysCalendarSet",
                    "type": "event"
                },
                {
                    "anonymous": False,
                    "inputs": [
                        {
                            "indexed": True,
                            "internalType": "string",
                            "name": "newRatingIndexed",
                            "type": "string"
                        },
                        {
                            "indexed": False,
                            "internalType": "string",
                            "name": "newRating",
                            "type": "string"
                        }
                    ],
                    "name": "RatingSet",
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
                            "internalType": "contract IRuleEngine",
                            "name": "newRuleEngine",
                            "type": "address"
                        }
                    ],
                    "name": "RuleEngineSet",
                    "type": "event"
                },
                {
                    "anonymous": False,
                    "inputs": [
                        {
                            "indexed": True,
                            "internalType": "uint256",
                            "name": "oldTime",
                            "type": "uint256"
                        },
                        {
                            "indexed": True,
                            "internalType": "uint256",
                            "name": "newTime",
                            "type": "uint256"
                        }
                    ],
                    "name": "SnapshotSchedule",
                    "type": "event"
                },
                {
                    "anonymous": False,
                    "inputs": [
                        {
                            "indexed": True,
                            "internalType": "uint256",
                            "name": "time",
                            "type": "uint256"
                        }
                    ],
                    "name": "SnapshotUnschedule",
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
                            "name": "spender",
                            "type": "address"
                        },
                        {
                            "indexed": False,
                            "internalType": "uint256",
                            "name": "amount",
                            "type": "uint256"
                        }
                    ],
                    "name": "Spend",
                    "type": "event"
                },
                {
                    "anonymous": False,
                    "inputs": [
                        {
                            "indexed": True,
                            "internalType": "string",
                            "name": "newTermIndexed",
                            "type": "string"
                        },
                        {
                            "indexed": False,
                            "internalType": "string",
                            "name": "newTerm",
                            "type": "string"
                        }
                    ],
                    "name": "TermSet",
                    "type": "event"
                },
                {
                    "anonymous": False,
                    "inputs": [
                        {
                            "indexed": True,
                            "internalType": "string",
                            "name": "newTokenIdIndexed",
                            "type": "string"
                        },
                        {
                            "indexed": False,
                            "internalType": "string",
                            "name": "newTokenId",
                            "type": "string"
                        }
                    ],
                    "name": "TokenIdSet",
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
                            "indexed": True,
                            "internalType": "address",
                            "name": "enforcer",
                            "type": "address"
                        },
                        {
                            "indexed": True,
                            "internalType": "address",
                            "name": "owner",
                            "type": "address"
                        },
                        {
                            "indexed": True,
                            "internalType": "string",
                            "name": "reasonIndexed",
                            "type": "string"
                        },
                        {
                            "indexed": False,
                            "internalType": "string",
                            "name": "reason",
                            "type": "string"
                        }
                    ],
                    "name": "Unfreeze",
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
                    "name": "BURNER_ROLE",
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
                    "name": "DEBT_CREDIT_EVENT_ROLE",
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
                    "name": "DEBT_ROLE",
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
                    "name": "ENFORCER_ROLE",
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
                    "inputs": [],
                    "name": "SNAPSHOOTER_ROLE",
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
                            "name": "spender",
                            "type": "address"
                        },
                        {
                            "internalType": "uint256",
                            "name": "amount",
                            "type": "uint256"
                        },
                        {
                            "internalType": "uint256",
                            "name": "currentAllowance",
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
                    "inputs": [],
                    "name": "creditEvents",
                    "outputs": [
                        {
                            "internalType": "bool",
                            "name": "flagDefault",
                            "type": "bool"
                        },
                        {
                            "internalType": "bool",
                            "name": "flagRedeemed",
                            "type": "bool"
                        },
                        {
                            "internalType": "string",
                            "name": "rating",
                            "type": "string"
                        }
                    ],
                    "stateMutability": "view",
                    "type": "function"
                },
                {
                    "inputs": [],
                    "name": "debt",
                    "outputs": [
                        {
                            "internalType": "uint256",
                            "name": "interestRate",
                            "type": "uint256"
                        },
                        {
                            "internalType": "uint256",
                            "name": "parValue",
                            "type": "uint256"
                        },
                        {
                            "internalType": "string",
                            "name": "guarantor",
                            "type": "string"
                        },
                        {
                            "internalType": "string",
                            "name": "bondHolder",
                            "type": "string"
                        },
                        {
                            "internalType": "string",
                            "name": "maturityDate",
                            "type": "string"
                        },
                        {
                            "internalType": "string",
                            "name": "interestScheduleFormat",
                            "type": "string"
                        },
                        {
                            "internalType": "string",
                            "name": "interestPaymentDate",
                            "type": "string"
                        },
                        {
                            "internalType": "string",
                            "name": "dayCountConvention",
                            "type": "string"
                        },
                        {
                            "internalType": "string",
                            "name": "businessDayConvention",
                            "type": "string"
                        },
                        {
                            "internalType": "string",
                            "name": "publicHolidayCalendar",
                            "type": "string"
                        },
                        {
                            "internalType": "string",
                            "name": "issuanceDate",
                            "type": "string"
                        },
                        {
                            "internalType": "string",
                            "name": "couponFrequency",
                            "type": "string"
                        }
                    ],
                    "stateMutability": "view",
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
                            "name": "amount",
                            "type": "uint256"
                        }
                    ],
                    "name": "detectTransferRestriction",
                    "outputs": [
                        {
                            "internalType": "uint8",
                            "name": "code",
                            "type": "uint8"
                        }
                    ],
                    "stateMutability": "view",
                    "type": "function"
                },
                {
                    "inputs": [],
                    "name": "flag",
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
                            "name": "account",
                            "type": "address"
                        },
                        {
                            "internalType": "uint256",
                            "name": "amount",
                            "type": "uint256"
                        }
                    ],
                    "name": "forceBurn",
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
                            "internalType": "string",
                            "name": "reason",
                            "type": "string"
                        }
                    ],
                    "name": "freeze",
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
                    "name": "frozen",
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
                    "name": "getAllSnapshots",
                    "outputs": [
                        {
                            "internalType": "uint256[]",
                            "name": "",
                            "type": "uint256[]"
                        }
                    ],
                    "stateMutability": "view",
                    "type": "function"
                },
                {
                    "inputs": [],
                    "name": "getNextSnapshots",
                    "outputs": [
                        {
                            "internalType": "uint256[]",
                            "name": "",
                            "type": "uint256[]"
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
                    "name": "information",
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
                            "internalType": "bool",
                            "name": "deployedWithProxyIrrevocable_",
                            "type": "bool"
                        },
                        {
                            "internalType": "address",
                            "name": "admin",
                            "type": "address"
                        },
                        {
                            "internalType": "string",
                            "name": "nameIrrevocable",
                            "type": "string"
                        },
                        {
                            "internalType": "string",
                            "name": "symbolIrrevocable",
                            "type": "string"
                        },
                        {
                            "internalType": "string",
                            "name": "tokenId",
                            "type": "string"
                        },
                        {
                            "internalType": "string",
                            "name": "terms",
                            "type": "string"
                        },
                        {
                            "internalType": "contract IRuleEngine",
                            "name": "ruleEngine",
                            "type": "address"
                        },
                        {
                            "internalType": "string",
                            "name": "information",
                            "type": "string"
                        },
                        {
                            "internalType": "uint256",
                            "name": "flag",
                            "type": "uint256"
                        }
                    ],
                    "name": "initialize",
                    "outputs": [],
                    "stateMutability": "nonpayable",
                    "type": "function"
                },
                {
                    "inputs": [
                        {
                            "internalType": "address",
                            "name": "forwarder",
                            "type": "address"
                        }
                    ],
                    "name": "isTrustedForwarder",
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
                    "name": "kill",
                    "outputs": [],
                    "stateMutability": "nonpayable",
                    "type": "function"
                },
                {
                    "inputs": [
                        {
                            "internalType": "uint8",
                            "name": "restrictionCode",
                            "type": "uint8"
                        }
                    ],
                    "name": "messageForTransferRestriction",
                    "outputs": [
                        {
                            "internalType": "string",
                            "name": "message",
                            "type": "string"
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
                            "name": "amount",
                            "type": "uint256"
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
                            "internalType": "uint256",
                            "name": "oldTime",
                            "type": "uint256"
                        },
                        {
                            "internalType": "uint256",
                            "name": "newTime",
                            "type": "uint256"
                        }
                    ],
                    "name": "rescheduleSnapshot",
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
                    "inputs": [],
                    "name": "ruleEngine",
                    "outputs": [
                        {
                            "internalType": "contract IRuleEngine",
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
                            "internalType": "uint256",
                            "name": "time",
                            "type": "uint256"
                        }
                    ],
                    "name": "scheduleSnapshot",
                    "outputs": [],
                    "stateMutability": "nonpayable",
                    "type": "function"
                },
                {
                    "inputs": [
                        {
                            "internalType": "uint256",
                            "name": "time",
                            "type": "uint256"
                        }
                    ],
                    "name": "scheduleSnapshotNotOptimized",
                    "outputs": [],
                    "stateMutability": "nonpayable",
                    "type": "function"
                },
                {
                    "inputs": [
                        {
                            "internalType": "string",
                            "name": "bondHolder_",
                            "type": "string"
                        }
                    ],
                    "name": "setBondHolder",
                    "outputs": [],
                    "stateMutability": "nonpayable",
                    "type": "function"
                },
                {
                    "inputs": [
                        {
                            "internalType": "string",
                            "name": "businessDayConvention_",
                            "type": "string"
                        }
                    ],
                    "name": "setBusinessDayConvention",
                    "outputs": [],
                    "stateMutability": "nonpayable",
                    "type": "function"
                },
                {
                    "inputs": [
                        {
                            "internalType": "string",
                            "name": "couponFrequency_",
                            "type": "string"
                        }
                    ],
                    "name": "setCouponFrequency",
                    "outputs": [],
                    "stateMutability": "nonpayable",
                    "type": "function"
                },
                {
                    "inputs": [
                        {
                            "internalType": "bool",
                            "name": "flagDefault_",
                            "type": "bool"
                        },
                        {
                            "internalType": "bool",
                            "name": "flagRedeemed_",
                            "type": "bool"
                        },
                        {
                            "internalType": "string",
                            "name": "rating_",
                            "type": "string"
                        }
                    ],
                    "name": "setCreditEvents",
                    "outputs": [],
                    "stateMutability": "nonpayable",
                    "type": "function"
                },
                {
                    "inputs": [
                        {
                            "internalType": "string",
                            "name": "dayCountConvention_",
                            "type": "string"
                        }
                    ],
                    "name": "setDayCountConvention",
                    "outputs": [],
                    "stateMutability": "nonpayable",
                    "type": "function"
                },
                {
                    "inputs": [
                        {
                            "internalType": "uint256",
                            "name": "interestRate_",
                            "type": "uint256"
                        },
                        {
                            "internalType": "uint256",
                            "name": "parValue_",
                            "type": "uint256"
                        },
                        {
                            "internalType": "string",
                            "name": "guarantor_",
                            "type": "string"
                        },
                        {
                            "internalType": "string",
                            "name": "bondHolder_",
                            "type": "string"
                        },
                        {
                            "internalType": "string",
                            "name": "maturityDate_",
                            "type": "string"
                        },
                        {
                            "internalType": "string",
                            "name": "interestScheduleFormat_",
                            "type": "string"
                        },
                        {
                            "internalType": "string",
                            "name": "interestPaymentDate_",
                            "type": "string"
                        },
                        {
                            "internalType": "string",
                            "name": "dayCountConvention_",
                            "type": "string"
                        },
                        {
                            "internalType": "string",
                            "name": "businessDayConvention_",
                            "type": "string"
                        },
                        {
                            "internalType": "string",
                            "name": "publicHolidayCalendar_",
                            "type": "string"
                        },
                        {
                            "internalType": "string",
                            "name": "issuanceDate_",
                            "type": "string"
                        },
                        {
                            "internalType": "string",
                            "name": "couponFrequency_",
                            "type": "string"
                        }
                    ],
                    "name": "setDebt",
                    "outputs": [],
                    "stateMutability": "nonpayable",
                    "type": "function"
                },
                {
                    "inputs": [
                        {
                            "internalType": "uint256",
                            "name": "flag_",
                            "type": "uint256"
                        }
                    ],
                    "name": "setFlag",
                    "outputs": [],
                    "stateMutability": "nonpayable",
                    "type": "function"
                },
                {
                    "inputs": [
                        {
                            "internalType": "bool",
                            "name": "flagDefault_",
                            "type": "bool"
                        }
                    ],
                    "name": "setFlagDefault",
                    "outputs": [],
                    "stateMutability": "nonpayable",
                    "type": "function"
                },
                {
                    "inputs": [
                        {
                            "internalType": "bool",
                            "name": "flagRedeemed_",
                            "type": "bool"
                        }
                    ],
                    "name": "setFlagRedeemed",
                    "outputs": [],
                    "stateMutability": "nonpayable",
                    "type": "function"
                },
                {
                    "inputs": [
                        {
                            "internalType": "string",
                            "name": "guarantor_",
                            "type": "string"
                        }
                    ],
                    "name": "setGuarantor",
                    "outputs": [],
                    "stateMutability": "nonpayable",
                    "type": "function"
                },
                {
                    "inputs": [
                        {
                            "internalType": "string",
                            "name": "information_",
                            "type": "string"
                        }
                    ],
                    "name": "setInformation",
                    "outputs": [],
                    "stateMutability": "nonpayable",
                    "type": "function"
                },
                {
                    "inputs": [
                        {
                            "internalType": "string",
                            "name": "interestPaymentDate_",
                            "type": "string"
                        }
                    ],
                    "name": "setInterestPaymentDate",
                    "outputs": [],
                    "stateMutability": "nonpayable",
                    "type": "function"
                },
                {
                    "inputs": [
                        {
                            "internalType": "uint256",
                            "name": "interestRate_",
                            "type": "uint256"
                        }
                    ],
                    "name": "setInterestRate",
                    "outputs": [],
                    "stateMutability": "nonpayable",
                    "type": "function"
                },
                {
                    "inputs": [
                        {
                            "internalType": "string",
                            "name": "interestScheduleFormat_",
                            "type": "string"
                        }
                    ],
                    "name": "setInterestScheduleFormat",
                    "outputs": [],
                    "stateMutability": "nonpayable",
                    "type": "function"
                },
                {
                    "inputs": [
                        {
                            "internalType": "string",
                            "name": "issuanceDate_",
                            "type": "string"
                        }
                    ],
                    "name": "setIssuanceDate",
                    "outputs": [],
                    "stateMutability": "nonpayable",
                    "type": "function"
                },
                {
                    "inputs": [
                        {
                            "internalType": "string",
                            "name": "maturityDate_",
                            "type": "string"
                        }
                    ],
                    "name": "setMaturityDate",
                    "outputs": [],
                    "stateMutability": "nonpayable",
                    "type": "function"
                },
                {
                    "inputs": [
                        {
                            "internalType": "uint256",
                            "name": "parValue_",
                            "type": "uint256"
                        }
                    ],
                    "name": "setParValue",
                    "outputs": [],
                    "stateMutability": "nonpayable",
                    "type": "function"
                },
                {
                    "inputs": [
                        {
                            "internalType": "string",
                            "name": "publicHolidayCalendar_",
                            "type": "string"
                        }
                    ],
                    "name": "setPublicHolidaysCalendar",
                    "outputs": [],
                    "stateMutability": "nonpayable",
                    "type": "function"
                },
                {
                    "inputs": [
                        {
                            "internalType": "string",
                            "name": "rating_",
                            "type": "string"
                        }
                    ],
                    "name": "setRating",
                    "outputs": [],
                    "stateMutability": "nonpayable",
                    "type": "function"
                },
                {
                    "inputs": [
                        {
                            "internalType": "contract IRuleEngine",
                            "name": "ruleEngine_",
                            "type": "address"
                        }
                    ],
                    "name": "setRuleEngine",
                    "outputs": [],
                    "stateMutability": "nonpayable",
                    "type": "function"
                },
                {
                    "inputs": [
                        {
                            "internalType": "string",
                            "name": "terms_",
                            "type": "string"
                        }
                    ],
                    "name": "setTerms",
                    "outputs": [],
                    "stateMutability": "nonpayable",
                    "type": "function"
                },
                {
                    "inputs": [
                        {
                            "internalType": "string",
                            "name": "tokenId_",
                            "type": "string"
                        }
                    ],
                    "name": "setTokenId",
                    "outputs": [],
                    "stateMutability": "nonpayable",
                    "type": "function"
                },
                {
                    "inputs": [
                        {
                            "internalType": "uint256",
                            "name": "time",
                            "type": "uint256"
                        },
                        {
                            "internalType": "address",
                            "name": "owner",
                            "type": "address"
                        }
                    ],
                    "name": "snapshotBalanceOf",
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
                            "name": "time",
                            "type": "uint256"
                        }
                    ],
                    "name": "snapshotTotalSupply",
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
                    "inputs": [],
                    "name": "terms",
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
                    "name": "tokenId",
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
                            "name": "to",
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
                            "name": "newAdmin",
                            "type": "address"
                        }
                    ],
                    "name": "transferAdminship",
                    "outputs": [],
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
                },
                {
                    "inputs": [
                        {
                            "internalType": "address",
                            "name": "account",
                            "type": "address"
                        },
                        {
                            "internalType": "string",
                            "name": "reason",
                            "type": "string"
                        }
                    ],
                    "name": "unfreeze",
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
                    "name": "unpause",
                    "outputs": [],
                    "stateMutability": "nonpayable",
                    "type": "function"
                },
                {
                    "inputs": [
                        {
                            "internalType": "uint256",
                            "name": "time",
                            "type": "uint256"
                        }
                    ],
                    "name": "unscheduleLastSnapshot",
                    "outputs": [],
                    "stateMutability": "nonpayable",
                    "type": "function"
                },
                {
                    "inputs": [
                        {
                            "internalType": "uint256",
                            "name": "time",
                            "type": "uint256"
                        }
                    ],
                    "name": "unscheduleSnapshotNotOptimized",
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
                            "name": "amount",
                            "type": "uint256"
                        }
                    ],
                    "name": "validateTransfer",
                    "outputs": [
                        {
                            "internalType": "bool",
                            "name": "",
                            "type": "bool"
                        }
                    ],
                    "stateMutability": "view",
                    "type": "function"
                }
            ]

if __name__ == '__main__':
   erc = Erc721("", "ether", "testnet")
   erc.connect()
