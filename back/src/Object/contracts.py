from web3 import Web3
from web3 import exceptions
from web3.middleware import geth_poa_middleware
from hexbytes import HexBytes
import os
import json

mnemonic = str(os.getenv('MNEMONIC', ''))

class W3:
    def __init__(self, network_type = 'ether', network = 'testnet'):
        self.networks = {
            "polygon": {
                "mainnet": "https://polygon-rpc.com",
                "testnet": "https://rpc-mumbai.matic.today"
            },
            "ether": {
                "testnet": "https://ropsten.infura.io/v3/9aa3d95b3bc440fa88ea12eaa4456161"
            }
        }
        self.network_type = 'ether' if network_type == None else network_type
        self.network = 'testnet' if network == None else network
        self.link = Web3()

    def is_connected(self):
        return self.link.isConnected()

    def connect(self, network_type = None, network = None):
        self.network_type = network_type if network_type != None else self.network_type
        self.network = network if network != None else self.network
        print(self.network_type, self.network)
        if self.network_type not in self.networks \
            or self.network not in self.networks[self.network_type]:
            return [False, "invalid connection argument", 400]
        provider = self.networks[self.network_type][self.network]
        self.link = Web3(Web3.HTTPProvider(provider))
        self.link.middleware_onion.inject(geth_poa_middleware, layer=0)
        self.link.eth.account.enable_unaudited_hdwallet_features()
        return [True, f"Connected to {provider}", None]

    def execute_transaction(self, transaction, owner_address, owner_key, additionnal_gas = 0):
        gas_cost = transaction.estimateGas()
        gas_cost = gas_cost + additionnal_gas
        gas_price = self.link.toWei(150, 'gwei')
        ether_cost = float(self.link.fromWei(gas_price * gas_cost, 'ether'))
        build = transaction.buildTransaction({
          'gas': gas_cost,
          'gasPrice': gas_price,
          'nonce': self.link.eth.getTransactionCount(owner_address, "pending")
        })
        signed_txn = self.link.eth.account.signTransaction(build, private_key=owner_key)
        txn = self.link.eth.sendRawTransaction(signed_txn.rawTransaction).hex()
        txn_receipt = self.link.eth.waitForTransactionReceipt(txn)
        txn_receipt = self.hextojson(txn_receipt)
        return [True, {"transact": txn, "cost": ether_cost, 'return': txn_receipt}, None]

    def hextojson(self, data):
        class HexJsonEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, HexBytes):
                    return obj.hex()
                if isinstance(obj, decimal.Decimal):
                    return float(obj)
                return super().default(obj)
        return json.loads(json.dumps(dict(data), cls=HexJsonEncoder))

    def owner(self):
        return self.link.eth.account.from_mnemonic(mnemonic)

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

    def get_contract(self):
        return self.link.eth.contract(self.address, abi=self.abi)

    def get_functions(self):
        functions = [i for i in self.abi if 'type' in i and i['type'] == 'function']
        for function in functions:
            del function['outputs']
            del function['stateMutability']
            del function['type']
        return [True, functions, None]

    def exec_function(self, name, kwargs):
        owner = self.owner()
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
        return self.execute_transaction(transaction, owner.address, owner.key)

    def get_constructor(self):
        constructor = [i for i in self.abi if 'type' in i and i['type'] == 'constructor']
        if len(constructor) > 0:
            constructor = constructor[0]['inputs']
        return [True, constructor, None]

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
        return self.execute_transaction(transaction, owner.address, owner.key)

class Erc20(Contract):
    def __init__(self, address,  network_type = None, network = None):
         super().__init__(address, network_type = network_type, network = network)
         self.bytecode = "60806040523480156200001157600080fd5b5060405162001a0038038062001a00833981810160405260808110156200003757600080fd5b81019080805160405193929190846401000000008211156200005857600080fd5b838201915060208201858111156200006f57600080fd5b82518660018202830111640100000000821117156200008d57600080fd5b8083526020830192505050908051906020019080838360005b83811015620000c3578082015181840152602081019050620000a6565b50505050905090810190601f168015620000f15780820380516001836020036101000a031916815260200191505b50604052602001805160405193929190846401000000008211156200011557600080fd5b838201915060208201858111156200012c57600080fd5b82518660018202830111640100000000821117156200014a57600080fd5b8083526020830192505050908051906020019080838360005b838110156200018057808201518184015260208101905062000163565b50505050905090810190601f168015620001ae5780820380516001836020036101000a031916815260200191505b50604052602001805190602001909291908051906020019092919050505083838160039080519060200190620001e6929190620004a6565b508060049080519060200190620001ff929190620004a6565b506012600560006101000a81548160ff021916908360ff16021790555050506200023081836200023a60201b60201c565b505050506200054c565b600073ffffffffffffffffffffffffffffffffffffffff168273ffffffffffffffffffffffffffffffffffffffff161415620002de576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040180806020018281038252601f8152602001807f45524332303a206d696e7420746f20746865207a65726f20616464726573730081525060200191505060405180910390fd5b620002f2600083836200041860201b60201c565b6200030e816002546200041d60201b62000ab81790919060201c565b6002819055506200036c816000808573ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff168152602001908152602001600020546200041d60201b62000ab81790919060201c565b6000808473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff168152602001908152602001600020819055508173ffffffffffffffffffffffffffffffffffffffff16600073ffffffffffffffffffffffffffffffffffffffff167fddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef836040518082815260200191505060405180910390a35050565b505050565b6000808284019050838110156200049c576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040180806020018281038252601b8152602001807f536166654d6174683a206164646974696f6e206f766572666c6f77000000000081525060200191505060405180910390fd5b8091505092915050565b828054600181600116156101000203166002900490600052602060002090601f016020900481019282601f10620004e957805160ff19168380011785556200051a565b828001600101855582156200051a579182015b8281111562000519578251825591602001919060010190620004fc565b5b5090506200052991906200052d565b5090565b5b80821115620005485760008160009055506001016200052e565b5090565b6114a4806200055c6000396000f3fe608060405234801561001057600080fd5b50600436106100cf5760003560e01c806342966c681161008c57806395d89b411161006657806395d89b41146103b6578063a457c2d714610439578063a9059cbb1461049d578063dd62ed3e14610501576100cf565b806342966c68146102e257806370a082311461031057806379cc679014610368576100cf565b806306fdde03146100d4578063095ea7b31461015757806318160ddd146101bb57806323b872dd146101d9578063313ce5671461025d578063395093511461027e575b600080fd5b6100dc610579565b6040518080602001828103825283818151815260200191508051906020019080838360005b8381101561011c578082015181840152602081019050610101565b50505050905090810190601f1680156101495780820380516001836020036101000a031916815260200191505b509250505060405180910390f35b6101a36004803603604081101561016d57600080fd5b81019080803573ffffffffffffffffffffffffffffffffffffffff1690602001909291908035906020019092919050505061061b565b60405180821515815260200191505060405180910390f35b6101c3610639565b6040518082815260200191505060405180910390f35b610245600480360360608110156101ef57600080fd5b81019080803573ffffffffffffffffffffffffffffffffffffffff169060200190929190803573ffffffffffffffffffffffffffffffffffffffff16906020019092919080359060200190929190505050610643565b60405180821515815260200191505060405180910390f35b61026561071c565b604051808260ff16815260200191505060405180910390f35b6102ca6004803603604081101561029457600080fd5b81019080803573ffffffffffffffffffffffffffffffffffffffff16906020019092919080359060200190929190505050610733565b60405180821515815260200191505060405180910390f35b61030e600480360360208110156102f857600080fd5b81019080803590602001909291905050506107e6565b005b6103526004803603602081101561032657600080fd5b81019080803573ffffffffffffffffffffffffffffffffffffffff1690602001909291905050506107fa565b6040518082815260200191505060405180910390f35b6103b46004803603604081101561037e57600080fd5b81019080803573ffffffffffffffffffffffffffffffffffffffff16906020019092919080359060200190929190505050610842565b005b6103be6108a4565b6040518080602001828103825283818151815260200191508051906020019080838360005b838110156103fe5780820151818401526020810190506103e3565b50505050905090810190601f16801561042b5780820380516001836020036101000a031916815260200191505b509250505060405180910390f35b6104856004803603604081101561044f57600080fd5b81019080803573ffffffffffffffffffffffffffffffffffffffff16906020019092919080359060200190929190505050610946565b60405180821515815260200191505060405180910390f35b6104e9600480360360408110156104b357600080fd5b81019080803573ffffffffffffffffffffffffffffffffffffffff16906020019092919080359060200190929190505050610a13565b60405180821515815260200191505060405180910390f35b6105636004803603604081101561051757600080fd5b81019080803573ffffffffffffffffffffffffffffffffffffffff169060200190929190803573ffffffffffffffffffffffffffffffffffffffff169060200190929190505050610a31565b6040518082815260200191505060405180910390f35b606060038054600181600116156101000203166002900480601f0160208091040260200160405190810160405280929190818152602001828054600181600116156101000203166002900480156106115780601f106105e657610100808354040283529160200191610611565b820191906000526020600020905b8154815290600101906020018083116105f457829003601f168201915b5050505050905090565b600061062f610628610b40565b8484610b48565b6001905092915050565b6000600254905090565b6000610650848484610d3f565b6107118461065c610b40565b61070c8560405180606001604052806028815260200161139460289139600160008b73ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060006106c2610b40565b73ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff168152602001908152602001600020546110009092919063ffffffff16565b610b48565b600190509392505050565b6000600560009054906101000a900460ff16905090565b60006107dc610740610b40565b846107d78560016000610751610b40565b73ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060008973ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002054610ab890919063ffffffff16565b610b48565b6001905092915050565b6107f76107f1610b40565b826110ba565b50565b60008060008373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff168152602001908152602001600020549050919050565b6000610881826040518060600160405280602481526020016113bc602491396108728661086d610b40565b610a31565b6110009092919063ffffffff16565b90506108958361088f610b40565b83610b48565b61089f83836110ba565b505050565b606060048054600181600116156101000203166002900480601f01602080910402602001604051908101604052809291908181526020018280546001816001161561010002031660029004801561093c5780601f106109115761010080835404028352916020019161093c565b820191906000526020600020905b81548152906001019060200180831161091f57829003601f168201915b5050505050905090565b6000610a09610953610b40565b84610a048560405180606001604052806025815260200161144a602591396001600061097d610b40565b73ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060008a73ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff168152602001908152602001600020546110009092919063ffffffff16565b610b48565b6001905092915050565b6000610a27610a20610b40565b8484610d3f565b6001905092915050565b6000600160008473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060008373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002054905092915050565b600080828401905083811015610b36576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040180806020018281038252601b8152602001807f536166654d6174683a206164646974696f6e206f766572666c6f77000000000081525060200191505060405180910390fd5b8091505092915050565b600033905090565b600073ffffffffffffffffffffffffffffffffffffffff168373ffffffffffffffffffffffffffffffffffffffff161415610bce576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260248152602001806114266024913960400191505060405180910390fd5b600073ffffffffffffffffffffffffffffffffffffffff168273ffffffffffffffffffffffffffffffffffffffff161415610c54576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040180806020018281038252602281526020018061134c6022913960400191505060405180910390fd5b80600160008573ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060008473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff168152602001908152602001600020819055508173ffffffffffffffffffffffffffffffffffffffff168373ffffffffffffffffffffffffffffffffffffffff167f8c5be1e5ebec7d5bd14f71427d1e84f3dd0314c0f7b2291e5b200ac8c7c3b925836040518082815260200191505060405180910390a3505050565b600073ffffffffffffffffffffffffffffffffffffffff168373ffffffffffffffffffffffffffffffffffffffff161415610dc5576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260258152602001806114016025913960400191505060405180910390fd5b600073ffffffffffffffffffffffffffffffffffffffff168273ffffffffffffffffffffffffffffffffffffffff161415610e4b576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260238152602001806113076023913960400191505060405180910390fd5b610e5683838361127e565b610ec18160405180606001604052806026815260200161136e602691396000808773ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff168152602001908152602001600020546110009092919063ffffffff16565b6000808573ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002081905550610f54816000808573ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002054610ab890919063ffffffff16565b6000808473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff168152602001908152602001600020819055508173ffffffffffffffffffffffffffffffffffffffff168373ffffffffffffffffffffffffffffffffffffffff167fddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef836040518082815260200191505060405180910390a3505050565b60008383111582906110ad576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825283818151815260200191508051906020019080838360005b83811015611072578082015181840152602081019050611057565b50505050905090810190601f16801561109f5780820380516001836020036101000a031916815260200191505b509250505060405180910390fd5b5082840390509392505050565b600073ffffffffffffffffffffffffffffffffffffffff168273ffffffffffffffffffffffffffffffffffffffff161415611140576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260218152602001806113e06021913960400191505060405180910390fd5b61114c8260008361127e565b6111b78160405180606001604052806022815260200161132a602291396000808673ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff168152602001908152602001600020546110009092919063ffffffff16565b6000808473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1681526020019081526020016000208190555061120e8160025461128390919063ffffffff16565b600281905550600073ffffffffffffffffffffffffffffffffffffffff168273ffffffffffffffffffffffffffffffffffffffff167fddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef836040518082815260200191505060405180910390a35050565b505050565b6000828211156112fb576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040180806020018281038252601e8152602001807f536166654d6174683a207375627472616374696f6e206f766572666c6f77000081525060200191505060405180910390fd5b81830390509291505056fe45524332303a207472616e7366657220746f20746865207a65726f206164647265737345524332303a206275726e20616d6f756e7420657863656564732062616c616e636545524332303a20617070726f766520746f20746865207a65726f206164647265737345524332303a207472616e7366657220616d6f756e7420657863656564732062616c616e636545524332303a207472616e7366657220616d6f756e74206578636565647320616c6c6f77616e636545524332303a206275726e20616d6f756e74206578636565647320616c6c6f77616e636545524332303a206275726e2066726f6d20746865207a65726f206164647265737345524332303a207472616e736665722066726f6d20746865207a65726f206164647265737345524332303a20617070726f76652066726f6d20746865207a65726f206164647265737345524332303a2064656372656173656420616c6c6f77616e63652062656c6f77207a65726fa2646970667358221220ea8921b12623c1150abb5ad231a6e6344c748fe8ee89e35829a9d9077bb3ce3964736f6c634300060c0033"
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
         self.bytecode = "60806040523480156200001157600080fd5b5060405162003253380380620032538339818101604052810190620000379190620002d3565b60016000806301ffc9a760e01b7bffffffffffffffffffffffffffffffffffffffffffffffffffffffff1916815260200190815260200160002060006101000a81548160ff02191690831515021790555060016000806380ac58cd60e01b7bffffffffffffffffffffffffffffffffffffffffffffffffffffffff1916815260200190815260200160002060006101000a81548160ff0219169083151502179055506001600080635b5e139f60e01b7bffffffffffffffffffffffffffffffffffffffffffffffffffffffff1916815260200190815260200160002060006101000a81548160ff02191690831515021790555033600860006101000a81548173ffffffffffffffffffffffffffffffffffffffff021916908373ffffffffffffffffffffffffffffffffffffffff160217905550816005908051906020019062000183929190620001a5565b5080600690805190602001906200019c929190620001a5565b505050620004dc565b828054620001b390620003ed565b90600052602060002090601f016020900481019282620001d7576000855562000223565b82601f10620001f257805160ff191683800117855562000223565b8280016001018555821562000223579182015b828111156200022257825182559160200191906001019062000205565b5b50905062000232919062000236565b5090565b5b808211156200025157600081600090555060010162000237565b5090565b60006200026c620002668462000381565b62000358565b9050828152602081018484840111156200028b576200028a620004bc565b5b62000298848285620003b7565b509392505050565b600082601f830112620002b857620002b7620004b7565b5b8151620002ca84826020860162000255565b91505092915050565b60008060408385031215620002ed57620002ec620004c6565b5b600083015167ffffffffffffffff8111156200030e576200030d620004c1565b5b6200031c85828601620002a0565b925050602083015167ffffffffffffffff81111562000340576200033f620004c1565b5b6200034e85828601620002a0565b9150509250929050565b60006200036462000377565b905062000372828262000423565b919050565b6000604051905090565b600067ffffffffffffffff8211156200039f576200039e62000488565b5b620003aa82620004cb565b9050602081019050919050565b60005b83811015620003d7578082015181840152602081019050620003ba565b83811115620003e7576000848401525b50505050565b600060028204905060018216806200040657607f821691505b602082108114156200041d576200041c62000459565b5b50919050565b6200042e82620004cb565b810181811067ffffffffffffffff8211171562000450576200044f62000488565b5b80604052505050565b7f4e487b7100000000000000000000000000000000000000000000000000000000600052602260045260246000fd5b7f4e487b7100000000000000000000000000000000000000000000000000000000600052604160045260246000fd5b600080fd5b600080fd5b600080fd5b600080fd5b6000601f19601f8301169050919050565b612d6780620004ec6000396000f3fe608060405234801561001057600080fd5b50600436106101165760003560e01c80638da5cb5b116100a2578063c87b56dd11610071578063c87b56dd146102df578063d3fc98641461030f578063e985e9c51461032b578063f2fde38b1461035b578063f3fe3bc31461037757610116565b80638da5cb5b1461026b57806395d89b4114610289578063a22cb465146102a7578063b88d4fde146102c357610116565b806323b872dd116100e957806323b872dd146101b557806342842e0e146101d15780636352211e146101ed57806370a082311461021d578063860d248a1461024d57610116565b806301ffc9a71461011b57806306fdde031461014b578063081812fc14610169578063095ea7b314610199575b600080fd5b610135600480360381019061013091906128cd565b610395565b6040516101429190612a5a565b60405180910390f35b6101536103fc565b6040516101609190612a75565b60405180910390f35b610183600480360381019061017e9190612927565b61048e565b60405161019091906129f3565b60405180910390f35b6101b360048036038101906101ae9190612819565b6105a9565b005b6101cf60048036038101906101ca91906126fe565b61098c565b005b6101eb60048036038101906101e691906126fe565b610dde565b005b61020760048036038101906102029190612927565b610dfe565b60405161021491906129f3565b60405180910390f35b61023760048036038101906102329190612691565b610ee4565b6040516102449190612a97565b60405180910390f35b610255610f9e565b6040516102629190612a75565b60405180910390f35b610273610fd7565b60405161028091906129f3565b60405180910390f35b610291610ffd565b60405161029e9190612a75565b60405180910390f35b6102c160048036038101906102bc91906127d9565b61108f565b005b6102dd60048036038101906102d89190612751565b61118c565b005b6102f960048036038101906102f49190612927565b6111e3565b6040516103069190612a75565b60405180910390f35b61032960048036038101906103249190612859565b6112d3565b005b610345600480360381019061034091906126be565b6113fa565b6040516103529190612a5a565b60405180910390f35b61037560048036038101906103709190612691565b61148e565b005b61037f6116c0565b60405161038c9190612a75565b60405180910390f35b6000806000837bffffffffffffffffffffffffffffffffffffffffffffffffffffffff19167bffffffffffffffffffffffffffffffffffffffffffffffffffffffff1916815260200190815260200160002060009054906101000a900460ff169050919050565b60606005805461040b90612c1b565b80601f016020809104026020016040519081016040528092919081815260200182805461043790612c1b565b80156104845780601f1061045957610100808354040283529160200191610484565b820191906000526020600020905b81548152906001019060200180831161046757829003601f168201915b5050505050905090565b600081600073ffffffffffffffffffffffffffffffffffffffff166001600083815260200190815260200160002060009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1614156040518060400160405280600681526020017f30303330303200000000000000000000000000000000000000000000000000008152509061056c576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004016105639190612a75565b60405180910390fd5b506002600084815260200190815260200160002060009054906101000a900473ffffffffffffffffffffffffffffffffffffffff16915050919050565b8060006001600083815260200190815260200160002060009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1690503373ffffffffffffffffffffffffffffffffffffffff168173ffffffffffffffffffffffffffffffffffffffff1614806106a25750600460008273ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060003373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060009054906101000a900460ff165b6040518060400160405280600681526020017f303033303033000000000000000000000000000000000000000000000000000081525090610719576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004016107109190612a75565b60405180910390fd5b5082600073ffffffffffffffffffffffffffffffffffffffff166001600083815260200190815260200160002060009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1614156040518060400160405280600681526020017f3030333030320000000000000000000000000000000000000000000000000000815250906107f6576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004016107ed9190612a75565b60405180910390fd5b5060006001600086815260200190815260200160002060009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1690508073ffffffffffffffffffffffffffffffffffffffff168673ffffffffffffffffffffffffffffffffffffffff1614156040518060400160405280600681526020017f3030333030380000000000000000000000000000000000000000000000000000815250906108d6576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004016108cd9190612a75565b60405180910390fd5b50856002600087815260200190815260200160002060006101000a81548173ffffffffffffffffffffffffffffffffffffffff021916908373ffffffffffffffffffffffffffffffffffffffff160217905550848673ffffffffffffffffffffffffffffffffffffffff168273ffffffffffffffffffffffffffffffffffffffff167f8c5be1e5ebec7d5bd14f71427d1e84f3dd0314c0f7b2291e5b200ac8c7c3b92560405160405180910390a4505050505050565b8060006001600083815260200190815260200160002060009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1690503373ffffffffffffffffffffffffffffffffffffffff168173ffffffffffffffffffffffffffffffffffffffff161480610a5d57503373ffffffffffffffffffffffffffffffffffffffff166002600084815260200190815260200160002060009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16145b80610aee5750600460008273ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060003373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060009054906101000a900460ff165b6040518060400160405280600681526020017f303033303034000000000000000000000000000000000000000000000000000081525090610b65576040517f08c379a0000000000000000000000000000000000000000000000000000000008152600401610b5c9190612a75565b60405180910390fd5b5082600073ffffffffffffffffffffffffffffffffffffffff166001600083815260200190815260200160002060009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1614156040518060400160405280600681526020017f303033303032000000000000000000000000000000000000000000000000000081525090610c42576040517f08c379a0000000000000000000000000000000000000000000000000000000008152600401610c399190612a75565b60405180910390fd5b5060006001600086815260200190815260200160002060009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1690508673ffffffffffffffffffffffffffffffffffffffff168173ffffffffffffffffffffffffffffffffffffffff16146040518060400160405280600681526020017f303033303037000000000000000000000000000000000000000000000000000081525090610d21576040517f08c379a0000000000000000000000000000000000000000000000000000000008152600401610d189190612a75565b60405180910390fd5b50600073ffffffffffffffffffffffffffffffffffffffff168673ffffffffffffffffffffffffffffffffffffffff1614156040518060400160405280600681526020017f303033303031000000000000000000000000000000000000000000000000000081525090610dca576040517f08c379a0000000000000000000000000000000000000000000000000000000008152600401610dc19190612a75565b60405180910390fd5b50610dd586866116f9565b50505050505050565b610df9838383604051806020016040528060008152506117ae565b505050565b60006001600083815260200190815260200160002060009054906101000a900473ffffffffffffffffffffffffffffffffffffffff169050600073ffffffffffffffffffffffffffffffffffffffff168173ffffffffffffffffffffffffffffffffffffffff1614156040518060400160405280600681526020017f303033303032000000000000000000000000000000000000000000000000000081525090610ede576040517f08c379a0000000000000000000000000000000000000000000000000000000008152600401610ed59190612a75565b60405180910390fd5b50919050565b60008073ffffffffffffffffffffffffffffffffffffffff168273ffffffffffffffffffffffffffffffffffffffff1614156040518060400160405280600681526020017f303033303031000000000000000000000000000000000000000000000000000081525090610f8d576040517f08c379a0000000000000000000000000000000000000000000000000000000008152600401610f849190612a75565b60405180910390fd5b50610f9782611d7c565b9050919050565b6040518060400160405280600681526020017f303138303032000000000000000000000000000000000000000000000000000081525081565b600860009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1681565b60606006805461100c90612c1b565b80601f016020809104026020016040519081016040528092919081815260200182805461103890612c1b565b80156110855780601f1061105a57610100808354040283529160200191611085565b820191906000526020600020905b81548152906001019060200180831161106857829003601f168201915b5050505050905090565b80600460003373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060008473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060006101000a81548160ff0219169083151502179055508173ffffffffffffffffffffffffffffffffffffffff163373ffffffffffffffffffffffffffffffffffffffff167f17307eab39ab6107e8899845ad3d59bd9653f200f220920489ca2b5937696c31836040516111809190612a5a565b60405180910390a35050565b6111dc85858585858080601f016020809104026020016040519081016040528093929190818152602001838380828437600081840152601f19601f820116905080830192505050505050506117ae565b5050505050565b606081600073ffffffffffffffffffffffffffffffffffffffff166001600083815260200190815260200160002060009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1614156040518060400160405280600681526020017f3030333030320000000000000000000000000000000000000000000000000000815250906112c1576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004016112b89190612a75565b60405180910390fd5b506112cb83611dc5565b915050919050565b600860009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff163373ffffffffffffffffffffffffffffffffffffffff16146040518060400160405280600681526020017f30313830303100000000000000000000000000000000000000000000000000008152509061139b576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004016113929190612a75565b60405180910390fd5b506113a68484611e6a565b6113f48383838080601f016020809104026020016040519081016040528093929190818152602001838380828437600081840152601f19601f82011690508083019250505050505050612058565b50505050565b6000600460008473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060008373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060009054906101000a900460ff16905092915050565b600860009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff163373ffffffffffffffffffffffffffffffffffffffff16146040518060400160405280600681526020017f303138303031000000000000000000000000000000000000000000000000000081525090611556576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040161154d9190612a75565b60405180910390fd5b50600073ffffffffffffffffffffffffffffffffffffffff168173ffffffffffffffffffffffffffffffffffffffff1614156040518060400160405280600681526020017f3031383030320000000000000000000000000000000000000000000000000000815250906115ff576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004016115f69190612a75565b60405180910390fd5b508073ffffffffffffffffffffffffffffffffffffffff16600860009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff167f8be0079c531659141344cd1fd0a4f28419497f9722a3daafe3b4186f6b6457e060405160405180910390a380600860006101000a81548173ffffffffffffffffffffffffffffffffffffffff021916908373ffffffffffffffffffffffffffffffffffffffff16021790555050565b6040518060400160405280600681526020017f303138303031000000000000000000000000000000000000000000000000000081525081565b60006001600083815260200190815260200160002060009054906101000a900473ffffffffffffffffffffffffffffffffffffffff16905061173a82612162565b611744818361219b565b61174e8383612306565b818373ffffffffffffffffffffffffffffffffffffffff168273ffffffffffffffffffffffffffffffffffffffff167fddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef60405160405180910390a4505050565b8160006001600083815260200190815260200160002060009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1690503373ffffffffffffffffffffffffffffffffffffffff168173ffffffffffffffffffffffffffffffffffffffff16148061187f57503373ffffffffffffffffffffffffffffffffffffffff166002600084815260200190815260200160002060009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16145b806119105750600460008273ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060003373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060009054906101000a900460ff165b6040518060400160405280600681526020017f303033303034000000000000000000000000000000000000000000000000000081525090611987576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040161197e9190612a75565b60405180910390fd5b5083600073ffffffffffffffffffffffffffffffffffffffff166001600083815260200190815260200160002060009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1614156040518060400160405280600681526020017f303033303032000000000000000000000000000000000000000000000000000081525090611a64576040517f08c379a0000000000000000000000000000000000000000000000000000000008152600401611a5b9190612a75565b60405180910390fd5b5060006001600087815260200190815260200160002060009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1690508773ffffffffffffffffffffffffffffffffffffffff168173ffffffffffffffffffffffffffffffffffffffff16146040518060400160405280600681526020017f303033303037000000000000000000000000000000000000000000000000000081525090611b43576040517f08c379a0000000000000000000000000000000000000000000000000000000008152600401611b3a9190612a75565b60405180910390fd5b50600073ffffffffffffffffffffffffffffffffffffffff168773ffffffffffffffffffffffffffffffffffffffff1614156040518060400160405280600681526020017f303033303031000000000000000000000000000000000000000000000000000081525090611bec576040517f08c379a0000000000000000000000000000000000000000000000000000000008152600401611be39190612a75565b60405180910390fd5b50611bf787876116f9565b611c168773ffffffffffffffffffffffffffffffffffffffff1661248e565b15611d725760008773ffffffffffffffffffffffffffffffffffffffff1663150b7a02338b8a8a6040518563ffffffff1660e01b8152600401611c5c9493929190612a0e565b602060405180830381600087803b158015611c7657600080fd5b505af1158015611c8a573d6000803e3d6000fd5b505050506040513d601f19601f82011682018060405250810190611cae91906128fa565b905063150b7a0260e01b7bffffffffffffffffffffffffffffffffffffffffffffffffffffffff1916817bffffffffffffffffffffffffffffffffffffffffffffffffffffffff1916146040518060400160405280600681526020017f303033303035000000000000000000000000000000000000000000000000000081525090611d6f576040517f08c379a0000000000000000000000000000000000000000000000000000000008152600401611d669190612a75565b60405180910390fd5b50505b5050505050505050565b6000600360008373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff168152602001908152602001600020549050919050565b6060600760008381526020019081526020016000208054611de590612c1b565b80601f0160208091040260200160405190810160405280929190818152602001828054611e1190612c1b565b8015611e5e5780601f10611e3357610100808354040283529160200191611e5e565b820191906000526020600020905b815481529060010190602001808311611e4157829003601f168201915b50505050509050919050565b600073ffffffffffffffffffffffffffffffffffffffff168273ffffffffffffffffffffffffffffffffffffffff1614156040518060400160405280600681526020017f303033303031000000000000000000000000000000000000000000000000000081525090611f12576040517f08c379a0000000000000000000000000000000000000000000000000000000008152600401611f099190612a75565b60405180910390fd5b50600073ffffffffffffffffffffffffffffffffffffffff166001600083815260200190815260200160002060009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16146040518060400160405280600681526020017f303033303036000000000000000000000000000000000000000000000000000081525090611fed576040517f08c379a0000000000000000000000000000000000000000000000000000000008152600401611fe49190612a75565b60405180910390fd5b50611ff88282612306565b808273ffffffffffffffffffffffffffffffffffffffff16600073ffffffffffffffffffffffffffffffffffffffff167fddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef60405160405180910390a45050565b81600073ffffffffffffffffffffffffffffffffffffffff166001600083815260200190815260200160002060009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1614156040518060400160405280600681526020017f303033303032000000000000000000000000000000000000000000000000000081525090612134576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040161212b9190612a75565b60405180910390fd5b508160076000858152602001908152602001600020908051906020019061215c9291906124d9565b50505050565b6002600082815260200190815260200160002060006101000a81549073ffffffffffffffffffffffffffffffffffffffff021916905550565b8173ffffffffffffffffffffffffffffffffffffffff166001600083815260200190815260200160002060009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16146040518060400160405280600681526020017f303033303037000000000000000000000000000000000000000000000000000081525090612274576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040161226b9190612a75565b60405180910390fd5b506001600360008473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060008282546122c59190612b40565b925050819055506001600082815260200190815260200160002060006101000a81549073ffffffffffffffffffffffffffffffffffffffff02191690555050565b600073ffffffffffffffffffffffffffffffffffffffff166001600083815260200190815260200160002060009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16146040518060400160405280600681526020017f3030333030360000000000000000000000000000000000000000000000000000815250906123e0576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004016123d79190612a75565b60405180910390fd5b50816001600083815260200190815260200160002060006101000a81548173ffffffffffffffffffffffffffffffffffffffff021916908373ffffffffffffffffffffffffffffffffffffffff1602179055506001600360008473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060008282546124839190612aea565b925050819055505050565b60008060007fc5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a47060001b9050833f91506000801b82141580156124d05750808214155b92505050919050565b8280546124e590612c1b565b90600052602060002090601f016020900481019282612507576000855561254e565b82601f1061252057805160ff191683800117855561254e565b8280016001018555821561254e579182015b8281111561254d578251825591602001919060010190612532565b5b50905061255b919061255f565b5090565b5b80821115612578576000816000905550600101612560565b5090565b60008135905061258b81612cd5565b92915050565b6000813590506125a081612cec565b92915050565b6000813590506125b581612d03565b92915050565b6000815190506125ca81612d03565b92915050565b60008083601f8401126125e6576125e5612cb0565b5b8235905067ffffffffffffffff81111561260357612602612cab565b5b60208301915083600182028301111561261f5761261e612cb5565b5b9250929050565b60008083601f84011261263c5761263b612cb0565b5b8235905067ffffffffffffffff81111561265957612658612cab565b5b60208301915083600182028301111561267557612674612cb5565b5b9250929050565b60008135905061268b81612d1a565b92915050565b6000602082840312156126a7576126a6612cbf565b5b60006126b58482850161257c565b91505092915050565b600080604083850312156126d5576126d4612cbf565b5b60006126e38582860161257c565b92505060206126f48582860161257c565b9150509250929050565b60008060006060848603121561271757612716612cbf565b5b60006127258682870161257c565b93505060206127368682870161257c565b92505060406127478682870161267c565b9150509250925092565b60008060008060006080868803121561276d5761276c612cbf565b5b600061277b8882890161257c565b955050602061278c8882890161257c565b945050604061279d8882890161267c565b935050606086013567ffffffffffffffff8111156127be576127bd612cba565b5b6127ca888289016125d0565b92509250509295509295909350565b600080604083850312156127f0576127ef612cbf565b5b60006127fe8582860161257c565b925050602061280f85828601612591565b9150509250929050565b600080604083850312156128305761282f612cbf565b5b600061283e8582860161257c565b925050602061284f8582860161267c565b9150509250929050565b6000806000806060858703121561287357612872612cbf565b5b60006128818782880161257c565b94505060206128928782880161267c565b935050604085013567ffffffffffffffff8111156128b3576128b2612cba565b5b6128bf87828801612626565b925092505092959194509250565b6000602082840312156128e3576128e2612cbf565b5b60006128f1848285016125a6565b91505092915050565b6000602082840312156129105761290f612cbf565b5b600061291e848285016125bb565b91505092915050565b60006020828403121561293d5761293c612cbf565b5b600061294b8482850161267c565b91505092915050565b61295d81612b74565b82525050565b61296c81612b86565b82525050565b600061297d82612ab2565b6129878185612ac8565b9350612997818560208601612be8565b6129a081612cc4565b840191505092915050565b60006129b682612abd565b6129c08185612ad9565b93506129d0818560208601612be8565b6129d981612cc4565b840191505092915050565b6129ed81612bde565b82525050565b6000602082019050612a086000830184612954565b92915050565b6000608082019050612a236000830187612954565b612a306020830186612954565b612a3d60408301856129e4565b8181036060830152612a4f8184612972565b905095945050505050565b6000602082019050612a6f6000830184612963565b92915050565b60006020820190508181036000830152612a8f81846129ab565b905092915050565b6000602082019050612aac60008301846129e4565b92915050565b600081519050919050565b600081519050919050565b600082825260208201905092915050565b600082825260208201905092915050565b6000612af582612bde565b9150612b0083612bde565b9250827fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff03821115612b3557612b34612c4d565b5b828201905092915050565b6000612b4b82612bde565b9150612b5683612bde565b925082821015612b6957612b68612c4d565b5b828203905092915050565b6000612b7f82612bbe565b9050919050565b60008115159050919050565b60007fffffffff0000000000000000000000000000000000000000000000000000000082169050919050565b600073ffffffffffffffffffffffffffffffffffffffff82169050919050565b6000819050919050565b60005b83811015612c06578082015181840152602081019050612beb565b83811115612c15576000848401525b50505050565b60006002820490506001821680612c3357607f821691505b60208210811415612c4757612c46612c7c565b5b50919050565b7f4e487b7100000000000000000000000000000000000000000000000000000000600052601160045260246000fd5b7f4e487b7100000000000000000000000000000000000000000000000000000000600052602260045260246000fd5b600080fd5b600080fd5b600080fd5b600080fd5b600080fd5b6000601f19601f8301169050919050565b612cde81612b74565b8114612ce957600080fd5b50565b612cf581612b86565b8114612d0057600080fd5b50565b612d0c81612b92565b8114612d1757600080fd5b50565b612d2381612bde565b8114612d2e57600080fd5b5056fea2646970667358221220f780fc64e53032b0ea976d154f97c9114fdfe2361eac568843efcc651d437c9264736f6c63430008060033"
         self.abi = [
                    	{
                    		"inputs": [
                    			{
                    				"internalType": "string",
                    				"name": "name_",
                    				"type": "string"
                    			},
                    			{
                    				"internalType": "string",
                    				"name": "symbol_",
                    				"type": "string"
                    			}
                    		],
                    		"stateMutability": "nonpayable",
                    		"type": "constructor"
                    	},
                    	{
                    		"anonymous": false,
                    		"inputs": [
                    			{
                    				"indexed": true,
                    				"internalType": "address",
                    				"name": "_owner",
                    				"type": "address"
                    			},
                    			{
                    				"indexed": true,
                    				"internalType": "address",
                    				"name": "_approved",
                    				"type": "address"
                    			},
                    			{
                    				"indexed": true,
                    				"internalType": "uint256",
                    				"name": "_tokenId",
                    				"type": "uint256"
                    			}
                    		],
                    		"name": "Approval",
                    		"type": "event"
                    	},
                    	{
                    		"anonymous": false,
                    		"inputs": [
                    			{
                    				"indexed": true,
                    				"internalType": "address",
                    				"name": "_owner",
                    				"type": "address"
                    			},
                    			{
                    				"indexed": true,
                    				"internalType": "address",
                    				"name": "_operator",
                    				"type": "address"
                    			},
                    			{
                    				"indexed": false,
                    				"internalType": "bool",
                    				"name": "_approved",
                    				"type": "bool"
                    			}
                    		],
                    		"name": "ApprovalForAll",
                    		"type": "event"
                    	},
                    	{
                    		"anonymous": false,
                    		"inputs": [
                    			{
                    				"indexed": true,
                    				"internalType": "address",
                    				"name": "previousOwner",
                    				"type": "address"
                    			},
                    			{
                    				"indexed": true,
                    				"internalType": "address",
                    				"name": "newOwner",
                    				"type": "address"
                    			}
                    		],
                    		"name": "OwnershipTransferred",
                    		"type": "event"
                    	},
                    	{
                    		"anonymous": false,
                    		"inputs": [
                    			{
                    				"indexed": true,
                    				"internalType": "address",
                    				"name": "_from",
                    				"type": "address"
                    			},
                    			{
                    				"indexed": true,
                    				"internalType": "address",
                    				"name": "_to",
                    				"type": "address"
                    			},
                    			{
                    				"indexed": true,
                    				"internalType": "uint256",
                    				"name": "_tokenId",
                    				"type": "uint256"
                    			}
                    		],
                    		"name": "Transfer",
                    		"type": "event"
                    	},
                    	{
                    		"inputs": [],
                    		"name": "CANNOT_TRANSFER_TO_ZERO_ADDRESS",
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
                    		"name": "NOT_CURRENT_OWNER",
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
                    				"internalType": "address",
                    				"name": "_approved",
                    				"type": "address"
                    			},
                    			{
                    				"internalType": "uint256",
                    				"name": "_tokenId",
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
                    				"name": "_owner",
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
                    				"name": "_tokenId",
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
                    				"internalType": "address",
                    				"name": "_owner",
                    				"type": "address"
                    			},
                    			{
                    				"internalType": "address",
                    				"name": "_operator",
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
                    				"name": "_to",
                    				"type": "address"
                    			},
                    			{
                    				"internalType": "uint256",
                    				"name": "_tokenId",
                    				"type": "uint256"
                    			},
                    			{
                    				"internalType": "string",
                    				"name": "_uri",
                    				"type": "string"
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
                    				"name": "_name",
                    				"type": "string"
                    			}
                    		],
                    		"stateMutability": "view",
                    		"type": "function"
                    	},
                    	{
                    		"inputs": [],
                    		"name": "owner",
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
                    				"internalType": "uint256",
                    				"name": "_tokenId",
                    				"type": "uint256"
                    			}
                    		],
                    		"name": "ownerOf",
                    		"outputs": [
                    			{
                    				"internalType": "address",
                    				"name": "_owner",
                    				"type": "address"
                    			}
                    		],
                    		"stateMutability": "view",
                    		"type": "function"
                    	},
                    	{
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
                    				"name": "_tokenId",
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
                    				"name": "_tokenId",
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
                    				"name": "_operator",
                    				"type": "address"
                    			},
                    			{
                    				"internalType": "bool",
                    				"name": "_approved",
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
                    				"name": "_interfaceID",
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
                    				"name": "_symbol",
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
                    				"name": "_tokenId",
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
                    				"name": "_tokenId",
                    				"type": "uint256"
                    			}
                    		],
                    		"name": "transferFrom",
                    		"outputs": [],
                    		"stateMutability": "nonpayable",
                    		"type": "function"
                    	},
                    	{
                    		"inputs": [
                    			{
                    				"internalType": "address",
                    				"name": "_newOwner",
                    				"type": "address"
                    			}
                    		],
                    		"name": "transferOwnership",
                    		"outputs": [],
                    		"stateMutability": "nonpayable",
                    		"type": "function"
                    	}
                    ]

if __name__ == '__main__':
   erc = Erc721("", "ether", "testnet")
   erc.connect()
   print(erc.is_connected())
   # print(erc.get_functions())
   print(erc.exec_function('balanceOf', {'owner': '0x781aD19FADc0482115D53ae660A76B852Ac8c276'}))
