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
        print({"transact": txn, "cost": ether_cost, 'return': txn_receipt})
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
        functions = [i for i in self.abi if 'type' in i and i['type'] == 'function']
        print([function['name'] for function in functions])
        if name not in [function['name'] for function in functions]:
            return [False, "Invalid function name", 400]
        for function in functions:
            if function['name'] == name:
                keep_function = function
        for elem in keep_function['inputs']:
            name = elem['name']
            type = elem['type']
            if name not in kwargs:
                return [False, f"missing {name}:{type}", 400]
        contract = self.link.eth.contract(self.address, abi=self.abi)
        transaction = contract.find_functions_by_name(name)(**kwargs)
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
         self.bytecode = "60806040523480156200001157600080fd5b5060405162002b3338038062002b33833981810160405260408110156200003757600080fd5b81019080805160405193929190846401000000008211156200005857600080fd5b838201915060208201858111156200006f57600080fd5b82518660018202830111640100000000821117156200008d57600080fd5b8083526020830192505050908051906020019080838360005b83811015620000c3578082015181840152602081019050620000a6565b50505050905090810190601f168015620000f15780820380516001836020036101000a031916815260200191505b50604052602001805160405193929190846401000000008211156200011557600080fd5b838201915060208201858111156200012c57600080fd5b82518660018202830111640100000000821117156200014a57600080fd5b8083526020830192505050908051906020019080838360005b838110156200018057808201518184015260208101905062000163565b50505050905090810190601f168015620001ae5780820380516001836020036101000a031916815260200191505b50604052505050620001cd6301ffc9a760e01b6200024f60201b60201c565b8160069080519060200190620001e592919062000358565b508060079080519060200190620001fe92919062000358565b50620002176380ac58cd60e01b6200024f60201b60201c565b6200022f635b5e139f60e01b6200024f60201b60201c565b6200024763780e9d6360e01b6200024f60201b60201c565b5050620003fe565b63ffffffff60e01b817bffffffffffffffffffffffffffffffffffffffffffffffffffffffff19161415620002ec576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040180806020018281038252601c8152602001807f4552433136353a20696e76616c696420696e746572666163652069640000000081525060200191505060405180910390fd5b6001600080837bffffffffffffffffffffffffffffffffffffffffffffffffffffffff19167bffffffffffffffffffffffffffffffffffffffffffffffffffffffff1916815260200190815260200160002060006101000a81548160ff02191690831515021790555050565b828054600181600116156101000203166002900490600052602060002090601f016020900481019282601f106200039b57805160ff1916838001178555620003cc565b82800160010185558215620003cc579182015b82811115620003cb578251825591602001919060010190620003ae565b5b509050620003db9190620003df565b5090565b5b80821115620003fa576000816000905550600101620003e0565b5090565b612725806200040e6000396000f3fe608060405234801561001057600080fd5b506004361061010b5760003560e01c80634f6ccce7116100a257806395d89b411161007157806395d89b411461056d578063a22cb465146105f0578063b88d4fde14610640578063c87b56dd14610745578063e985e9c5146107ec5761010b565b80634f6ccce7146103f85780636352211e1461043a5780636c0360eb1461049257806370a08231146105155761010b565b806318160ddd116100de57806318160ddd1461029c57806323b872dd146102ba5780632f745c591461032857806342842e0e1461038a5761010b565b806301ffc9a71461011057806306fdde0314610173578063081812fc146101f6578063095ea7b31461024e575b600080fd5b61015b6004803603602081101561012657600080fd5b8101908080357bffffffffffffffffffffffffffffffffffffffffffffffffffffffff19169060200190929190505050610866565b60405180821515815260200191505060405180910390f35b61017b6108cd565b6040518080602001828103825283818151815260200191508051906020019080838360005b838110156101bb5780820151818401526020810190506101a0565b50505050905090810190601f1680156101e85780820380516001836020036101000a031916815260200191505b509250505060405180910390f35b6102226004803603602081101561020c57600080fd5b810190808035906020019092919050505061096f565b604051808273ffffffffffffffffffffffffffffffffffffffff16815260200191505060405180910390f35b61029a6004803603604081101561026457600080fd5b81019080803573ffffffffffffffffffffffffffffffffffffffff16906020019092919080359060200190929190505050610a0a565b005b6102a4610b4e565b6040518082815260200191505060405180910390f35b610326600480360360608110156102d057600080fd5b81019080803573ffffffffffffffffffffffffffffffffffffffff169060200190929190803573ffffffffffffffffffffffffffffffffffffffff16906020019092919080359060200190929190505050610b5f565b005b6103746004803603604081101561033e57600080fd5b81019080803573ffffffffffffffffffffffffffffffffffffffff16906020019092919080359060200190929190505050610bd5565b6040518082815260200191505060405180910390f35b6103f6600480360360608110156103a057600080fd5b81019080803573ffffffffffffffffffffffffffffffffffffffff169060200190929190803573ffffffffffffffffffffffffffffffffffffffff16906020019092919080359060200190929190505050610c30565b005b6104246004803603602081101561040e57600080fd5b8101908080359060200190929190505050610c50565b6040518082815260200191505060405180910390f35b6104666004803603602081101561045057600080fd5b8101908080359060200190929190505050610c73565b604051808273ffffffffffffffffffffffffffffffffffffffff16815260200191505060405180910390f35b61049a610caa565b6040518080602001828103825283818151815260200191508051906020019080838360005b838110156104da5780820151818401526020810190506104bf565b50505050905090810190601f1680156105075780820380516001836020036101000a031916815260200191505b509250505060405180910390f35b6105576004803603602081101561052b57600080fd5b81019080803573ffffffffffffffffffffffffffffffffffffffff169060200190929190505050610d4c565b6040518082815260200191505060405180910390f35b610575610e21565b6040518080602001828103825283818151815260200191508051906020019080838360005b838110156105b557808201518184015260208101905061059a565b50505050905090810190601f1680156105e25780820380516001836020036101000a031916815260200191505b509250505060405180910390f35b61063e6004803603604081101561060657600080fd5b81019080803573ffffffffffffffffffffffffffffffffffffffff169060200190929190803515159060200190929190505050610ec3565b005b6107436004803603608081101561065657600080fd5b81019080803573ffffffffffffffffffffffffffffffffffffffff169060200190929190803573ffffffffffffffffffffffffffffffffffffffff16906020019092919080359060200190929190803590602001906401000000008111156106bd57600080fd5b8201836020820111156106cf57600080fd5b803590602001918460018302840111640100000000831117156106f157600080fd5b91908080601f016020809104026020016040519081016040528093929190818152602001838380828437600081840152601f19601f820116905080830192505050505050509192919290505050611079565b005b6107716004803603602081101561075b57600080fd5b81019080803590602001909291905050506110f1565b6040518080602001828103825283818151815260200191508051906020019080838360005b838110156107b1578082015181840152602081019050610796565b50505050905090810190601f1680156107de5780820380516001836020036101000a031916815260200191505b509250505060405180910390f35b61084e6004803603604081101561080257600080fd5b81019080803573ffffffffffffffffffffffffffffffffffffffff169060200190929190803573ffffffffffffffffffffffffffffffffffffffff1690602001909291905050506113c2565b60405180821515815260200191505060405180910390f35b6000806000837bffffffffffffffffffffffffffffffffffffffffffffffffffffffff19167bffffffffffffffffffffffffffffffffffffffffffffffffffffffff1916815260200190815260200160002060009054906101000a900460ff169050919050565b606060068054600181600116156101000203166002900480601f0160208091040260200160405190810160405280929190818152602001828054600181600116156101000203166002900480156109655780601f1061093a57610100808354040283529160200191610965565b820191906000526020600020905b81548152906001019060200180831161094857829003601f168201915b5050505050905090565b600061097a82611456565b6109cf576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040180806020018281038252602c81526020018061261a602c913960400191505060405180910390fd5b6004600083815260200190815260200160002060009054906101000a900473ffffffffffffffffffffffffffffffffffffffff169050919050565b6000610a1582610c73565b90508073ffffffffffffffffffffffffffffffffffffffff168373ffffffffffffffffffffffffffffffffffffffff161415610a9c576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040180806020018281038252602181526020018061269e6021913960400191505060405180910390fd5b8073ffffffffffffffffffffffffffffffffffffffff16610abb611473565b73ffffffffffffffffffffffffffffffffffffffff161480610aea5750610ae981610ae4611473565b6113c2565b5b610b3f576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040180806020018281038252603881526020018061256d6038913960400191505060405180910390fd5b610b49838361147b565b505050565b6000610b5a6002611534565b905090565b610b70610b6a611473565b82611549565b610bc5576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260318152602001806126bf6031913960400191505060405180910390fd5b610bd083838361163d565b505050565b6000610c2882600160008673ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002061188090919063ffffffff16565b905092915050565b610c4b83838360405180602001604052806000815250611079565b505050565b600080610c6783600261189a90919063ffffffff16565b50905080915050919050565b6000610ca3826040518060600160405280602981526020016125cf6029913960026118c69092919063ffffffff16565b9050919050565b606060098054600181600116156101000203166002900480601f016020809104026020016040519081016040528092919081815260200182805460018160011615610100020316600290048015610d425780601f10610d1757610100808354040283529160200191610d42565b820191906000526020600020905b815481529060010190602001808311610d2557829003601f168201915b5050505050905090565b60008073ffffffffffffffffffffffffffffffffffffffff168273ffffffffffffffffffffffffffffffffffffffff161415610dd3576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040180806020018281038252602a8152602001806125a5602a913960400191505060405180910390fd5b610e1a600160008473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1681526020019081526020016000206118e5565b9050919050565b606060078054600181600116156101000203166002900480601f016020809104026020016040519081016040528092919081815260200182805460018160011615610100020316600290048015610eb95780601f10610e8e57610100808354040283529160200191610eb9565b820191906000526020600020905b815481529060010190602001808311610e9c57829003601f168201915b5050505050905090565b610ecb611473565b73ffffffffffffffffffffffffffffffffffffffff168273ffffffffffffffffffffffffffffffffffffffff161415610f6c576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260198152602001807f4552433732313a20617070726f766520746f2063616c6c65720000000000000081525060200191505060405180910390fd5b8060056000610f79611473565b73ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060008473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060006101000a81548160ff0219169083151502179055508173ffffffffffffffffffffffffffffffffffffffff16611026611473565b73ffffffffffffffffffffffffffffffffffffffff167f17307eab39ab6107e8899845ad3d59bd9653f200f220920489ca2b5937696c318360405180821515815260200191505060405180910390a35050565b61108a611084611473565b83611549565b6110df576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260318152602001806126bf6031913960400191505060405180910390fd5b6110eb848484846118fa565b50505050565b60606110fc82611456565b611151576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040180806020018281038252602f81526020018061266f602f913960400191505060405180910390fd5b6060600860008481526020019081526020016000208054600181600116156101000203166002900480601f0160208091040260200160405190810160405280929190818152602001828054600181600116156101000203166002900480156111fa5780601f106111cf576101008083540402835291602001916111fa565b820191906000526020600020905b8154815290600101906020018083116111dd57829003601f168201915b50505050509050606061120b610caa565b90506000815114156112215781925050506113bd565b6000825111156112f25780826040516020018083805190602001908083835b602083106112635780518252602082019150602081019050602083039250611240565b6001836020036101000a03801982511681845116808217855250505050505090500182805190602001908083835b602083106112b45780518252602082019150602081019050602083039250611291565b6001836020036101000a03801982511681845116808217855250505050505090500192505050604051602081830303815290604052925050506113bd565b806112fc8561196c565b6040516020018083805190602001908083835b60208310611332578051825260208201915060208101905060208303925061130f565b6001836020036101000a03801982511681845116808217855250505050505090500182805190602001908083835b602083106113835780518252602082019150602081019050602083039250611360565b6001836020036101000a03801982511681845116808217855250505050505090500192505050604051602081830303815290604052925050505b919050565b6000600560008473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060008373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060009054906101000a900460ff16905092915050565b600061146c826002611ab390919063ffffffff16565b9050919050565b600033905090565b816004600083815260200190815260200160002060006101000a81548173ffffffffffffffffffffffffffffffffffffffff021916908373ffffffffffffffffffffffffffffffffffffffff160217905550808273ffffffffffffffffffffffffffffffffffffffff166114ee83610c73565b73ffffffffffffffffffffffffffffffffffffffff167f8c5be1e5ebec7d5bd14f71427d1e84f3dd0314c0f7b2291e5b200ac8c7c3b92560405160405180910390a45050565b600061154282600001611acd565b9050919050565b600061155482611456565b6115a9576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040180806020018281038252602c815260200180612541602c913960400191505060405180910390fd5b60006115b483610c73565b90508073ffffffffffffffffffffffffffffffffffffffff168473ffffffffffffffffffffffffffffffffffffffff16148061162357508373ffffffffffffffffffffffffffffffffffffffff1661160b8461096f565b73ffffffffffffffffffffffffffffffffffffffff16145b80611634575061163381856113c2565b5b91505092915050565b8273ffffffffffffffffffffffffffffffffffffffff1661165d82610c73565b73ffffffffffffffffffffffffffffffffffffffff16146116c9576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260298152602001806126466029913960400191505060405180910390fd5b600073ffffffffffffffffffffffffffffffffffffffff168273ffffffffffffffffffffffffffffffffffffffff16141561174f576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260248152602001806124f76024913960400191505060405180910390fd5b61175a838383611ade565b61176560008261147b565b6117b681600160008673ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff168152602001908152602001600020611ae390919063ffffffff16565b5061180881600160008573ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff168152602001908152602001600020611afd90919063ffffffff16565b5061181f81836002611b179092919063ffffffff16565b50808273ffffffffffffffffffffffffffffffffffffffff168473ffffffffffffffffffffffffffffffffffffffff167fddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef60405160405180910390a4505050565b600061188f8360000183611b4c565b60001c905092915050565b6000806000806118ad8660000186611bcf565b915091508160001c8160001c9350935050509250929050565b60006118d9846000018460001b84611c68565b60001c90509392505050565b60006118f382600001611d5e565b9050919050565b61190584848461163d565b61191184848484611d6f565b611966576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260328152602001806124c56032913960400191505060405180910390fd5b50505050565b606060008214156119b4576040518060400160405280600181526020017f30000000000000000000000000000000000000000000000000000000000000008152509050611aae565b600082905060005b600082146119de578080600101915050600a82816119d657fe5b0491506119bc565b60608167ffffffffffffffff811180156119f757600080fd5b506040519080825280601f01601f191660200182016040528015611a2a5781602001600182028036833780820191505090505b50905060006001830390508593505b60008414611aa657600a8481611a4b57fe5b0660300160f81b82828060019003935081518110611a6557fe5b60200101907effffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff1916908160001a905350600a8481611a9e57fe5b049350611a39565b819450505050505b919050565b6000611ac5836000018360001b611f88565b905092915050565b600081600001805490509050919050565b505050565b6000611af5836000018360001b611fab565b905092915050565b6000611b0f836000018360001b612093565b905092915050565b6000611b43846000018460001b8473ffffffffffffffffffffffffffffffffffffffff1660001b612103565b90509392505050565b600081836000018054905011611bad576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260228152602001806124a36022913960400191505060405180910390fd5b826000018281548110611bbc57fe5b9060005260206000200154905092915050565b60008082846000018054905011611c31576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825260228152602001806125f86022913960400191505060405180910390fd5b6000846000018481548110611c4257fe5b906000526020600020906002020190508060000154816001015492509250509250929050565b60008084600101600085815260200190815260200160002054905060008114158390611d2f576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825283818151815260200191508051906020019080838360005b83811015611cf4578082015181840152602081019050611cd9565b50505050905090810190601f168015611d215780820380516001836020036101000a031916815260200191505b509250505060405180910390fd5b50846000016001820381548110611d4257fe5b9060005260206000209060020201600101549150509392505050565b600081600001805490509050919050565b6000611d908473ffffffffffffffffffffffffffffffffffffffff166121df565b611d9d5760019050611f80565b6060611f0763150b7a0260e01b611db2611473565b888787604051602401808573ffffffffffffffffffffffffffffffffffffffff1681526020018473ffffffffffffffffffffffffffffffffffffffff16815260200183815260200180602001828103825283818151815260200191508051906020019080838360005b83811015611e36578082015181840152602081019050611e1b565b50505050905090810190601f168015611e635780820380516001836020036101000a031916815260200191505b5095505050505050604051602081830303815290604052907bffffffffffffffffffffffffffffffffffffffffffffffffffffffff19166020820180517bffffffffffffffffffffffffffffffffffffffffffffffffffffffff83818316178352505050506040518060600160405280603281526020016124c5603291398773ffffffffffffffffffffffffffffffffffffffff166121f29092919063ffffffff16565b90506000818060200190516020811015611f2057600080fd5b8101908080519060200190929190505050905063150b7a0260e01b7bffffffffffffffffffffffffffffffffffffffffffffffffffffffff1916817bffffffffffffffffffffffffffffffffffffffffffffffffffffffff191614925050505b949350505050565b600080836001016000848152602001908152602001600020541415905092915050565b600080836001016000848152602001908152602001600020549050600081146120875760006001820390506000600186600001805490500390506000866000018281548110611ff657fe5b906000526020600020015490508087600001848154811061201357fe5b906000526020600020018190555060018301876001016000838152602001908152602001600020819055508660000180548061204b57fe5b6001900381819060005260206000200160009055905586600101600087815260200190815260200160002060009055600194505050505061208d565b60009150505b92915050565b600061209f838361220a565b6120f85782600001829080600181540180825580915050600190039060005260206000200160009091909190915055826000018054905083600101600084815260200190815260200160002081905550600190506120fd565b600090505b92915050565b60008084600101600085815260200190815260200160002054905060008114156121aa578460000160405180604001604052808681526020018581525090806001815401808255809150506001900390600052602060002090600202016000909190919091506000820151816000015560208201518160010155505084600001805490508560010160008681526020019081526020016000208190555060019150506121d8565b828560000160018303815481106121bd57fe5b90600052602060002090600202016001018190555060009150505b9392505050565b600080823b905060008111915050919050565b6060612201848460008561222d565b90509392505050565b600080836001016000848152602001908152602001600020541415905092915050565b606082471015612288576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040180806020018281038252602681526020018061251b6026913960400191505060405180910390fd5b612291856121df565b612303576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040180806020018281038252601d8152602001807f416464726573733a2063616c6c20746f206e6f6e2d636f6e747261637400000081525060200191505060405180910390fd5b600060608673ffffffffffffffffffffffffffffffffffffffff1685876040518082805190602001908083835b602083106123535780518252602082019150602081019050602083039250612330565b6001836020036101000a03801982511681845116808217855250505050505090500191505060006040518083038185875af1925050503d80600081146123b5576040519150601f19603f3d011682016040523d82523d6000602084013e6123ba565b606091505b50915091506123ca8282866123d6565b92505050949350505050565b606083156123e65782905061249b565b6000835111156123f95782518084602001fd5b816040517f08c379a00000000000000000000000000000000000000000000000000000000081526004018080602001828103825283818151815260200191508051906020019080838360005b83811015612460578082015181840152602081019050612445565b50505050905090810190601f16801561248d5780820380516001836020036101000a031916815260200191505b509250505060405180910390fd5b939250505056fe456e756d657261626c655365743a20696e646578206f7574206f6620626f756e64734552433732313a207472616e7366657220746f206e6f6e20455243373231526563656976657220696d706c656d656e7465724552433732313a207472616e7366657220746f20746865207a65726f2061646472657373416464726573733a20696e73756666696369656e742062616c616e636520666f722063616c6c4552433732313a206f70657261746f7220717565727920666f72206e6f6e6578697374656e7420746f6b656e4552433732313a20617070726f76652063616c6c6572206973206e6f74206f776e6572206e6f7220617070726f76656420666f7220616c6c4552433732313a2062616c616e636520717565727920666f7220746865207a65726f20616464726573734552433732313a206f776e657220717565727920666f72206e6f6e6578697374656e7420746f6b656e456e756d657261626c654d61703a20696e646578206f7574206f6620626f756e64734552433732313a20617070726f76656420717565727920666f72206e6f6e6578697374656e7420746f6b656e4552433732313a207472616e73666572206f6620746f6b656e2074686174206973206e6f74206f776e4552433732314d657461646174613a2055524920717565727920666f72206e6f6e6578697374656e7420746f6b656e4552433732313a20617070726f76616c20746f2063757272656e74206f776e65724552433732313a207472616e736665722063616c6c6572206973206e6f74206f776e6572206e6f7220617070726f766564a26469706673582212203ed357baf16d051d4ab729c3a75a4bace123a44366102718165ed505eb2a4d1b64736f6c634300060c0033"
         self.abi = [
                       {
                          "inputs":[
                             {
                                "internalType":"string",
                                "name":"name_",
                                "type":"string"
                             },
                             {
                                "internalType":"string",
                                "name":"symbol_",
                                "type":"string"
                             }
                          ],
                          "stateMutability":"nonpayable",
                          "type":"constructor"
                       },
                       {
                          "anonymous":False,
                          "inputs":[
                             {
                                "indexed":True,
                                "internalType":"address",
                                "name":"owner",
                                "type":"address"
                             },
                             {
                                "indexed":True,
                                "internalType":"address",
                                "name":"approved",
                                "type":"address"
                             },
                             {
                                "indexed":True,
                                "internalType":"uint256",
                                "name":"tokenId",
                                "type":"uint256"
                             }
                          ],
                          "name":"Approval",
                          "type":"event"
                       },
                       {
                          "anonymous":False,
                          "inputs":[
                             {
                                "indexed":True,
                                "internalType":"address",
                                "name":"owner",
                                "type":"address"
                             },
                             {
                                "indexed":True,
                                "internalType":"address",
                                "name":"operator",
                                "type":"address"
                             },
                             {
                                "indexed":False,
                                "internalType":"bool",
                                "name":"approved",
                                "type":"bool"
                             }
                          ],
                          "name":"ApprovalForAll",
                          "type":"event"
                       },
                       {
                          "anonymous":False,
                          "inputs":[
                             {
                                "indexed":True,
                                "internalType":"address",
                                "name":"from",
                                "type":"address"
                             },
                             {
                                "indexed":True,
                                "internalType":"address",
                                "name":"to",
                                "type":"address"
                             },
                             {
                                "indexed":True,
                                "internalType":"uint256",
                                "name":"tokenId",
                                "type":"uint256"
                             }
                          ],
                          "name":"Transfer",
                          "type":"event"
                       },
                       {
                          "inputs":[
                             {
                                "internalType":"address",
                                "name":"to",
                                "type":"address"
                             },
                             {
                                "internalType":"uint256",
                                "name":"tokenId",
                                "type":"uint256"
                             }
                          ],
                          "name":"approve",
                          "outputs":[

                          ],
                          "stateMutability":"nonpayable",
                          "type":"function"
                       },
                       {
                          "inputs":[
                             {
                                "internalType":"address",
                                "name":"owner",
                                "type":"address"
                             }
                          ],
                          "name":"balanceOf",
                          "outputs":[
                             {
                                "internalType":"uint256",
                                "name":"",
                                "type":"uint256"
                             }
                          ],
                          "stateMutability":"view",
                          "type":"function"
                       },
                       {
                          "inputs":[

                          ],
                          "name":"baseURI",
                          "outputs":[
                             {
                                "internalType":"string",
                                "name":"",
                                "type":"string"
                             }
                          ],
                          "stateMutability":"view",
                          "type":"function"
                       },
                       {
                          "inputs":[
                             {
                                "internalType":"uint256",
                                "name":"tokenId",
                                "type":"uint256"
                             }
                          ],
                          "name":"getApproved",
                          "outputs":[
                             {
                                "internalType":"address",
                                "name":"",
                                "type":"address"
                             }
                          ],
                          "stateMutability":"view",
                          "type":"function"
                       },
                       {
                          "inputs":[
                             {
                                "internalType":"address",
                                "name":"owner",
                                "type":"address"
                             },
                             {
                                "internalType":"address",
                                "name":"operator",
                                "type":"address"
                             }
                          ],
                          "name":"isApprovedForAll",
                          "outputs":[
                             {
                                "internalType":"bool",
                                "name":"",
                                "type":"bool"
                             }
                          ],
                          "stateMutability":"view",
                          "type":"function"
                       },
                       {
                          "inputs":[

                          ],
                          "name":"name",
                          "outputs":[
                             {
                                "internalType":"string",
                                "name":"",
                                "type":"string"
                             }
                          ],
                          "stateMutability":"view",
                          "type":"function"
                       },
                       {
                          "inputs":[
                             {
                                "internalType":"uint256",
                                "name":"tokenId",
                                "type":"uint256"
                             }
                          ],
                          "name":"ownerOf",
                          "outputs":[
                             {
                                "internalType":"address",
                                "name":"",
                                "type":"address"
                             }
                          ],
                          "stateMutability":"view",
                          "type":"function"
                       },
                       {
                          "inputs":[
                             {
                                "internalType":"address",
                                "name":"from",
                                "type":"address"
                             },
                             {
                                "internalType":"address",
                                "name":"to",
                                "type":"address"
                             },
                             {
                                "internalType":"uint256",
                                "name":"tokenId",
                                "type":"uint256"
                             }
                          ],
                          "name":"safeTransferFrom",
                          "outputs":[

                          ],
                          "stateMutability":"nonpayable",
                          "type":"function"
                       },
                       {
                          "inputs":[
                             {
                                "internalType":"address",
                                "name":"from",
                                "type":"address"
                             },
                             {
                                "internalType":"address",
                                "name":"to",
                                "type":"address"
                             },
                             {
                                "internalType":"uint256",
                                "name":"tokenId",
                                "type":"uint256"
                             },
                             {
                                "internalType":"bytes",
                                "name":"_data",
                                "type":"bytes"
                             }
                          ],
                          "name":"safeTransferFrom",
                          "outputs":[

                          ],
                          "stateMutability":"nonpayable",
                          "type":"function"
                       },
                       {
                          "inputs":[
                             {
                                "internalType":"address",
                                "name":"operator",
                                "type":"address"
                             },
                             {
                                "internalType":"bool",
                                "name":"approved",
                                "type":"bool"
                             }
                          ],
                          "name":"setApprovalForAll",
                          "outputs":[

                          ],
                          "stateMutability":"nonpayable",
                          "type":"function"
                       },
                       {
                          "inputs":[
                             {
                                "internalType":"bytes4",
                                "name":"interfaceId",
                                "type":"bytes4"
                             }
                          ],
                          "name":"supportsInterface",
                          "outputs":[
                             {
                                "internalType":"bool",
                                "name":"",
                                "type":"bool"
                             }
                          ],
                          "stateMutability":"view",
                          "type":"function"
                       },
                       {
                          "inputs":[

                          ],
                          "name":"symbol",
                          "outputs":[
                             {
                                "internalType":"string",
                                "name":"",
                                "type":"string"
                             }
                          ],
                          "stateMutability":"view",
                          "type":"function"
                       },
                       {
                          "inputs":[
                             {
                                "internalType":"uint256",
                                "name":"index",
                                "type":"uint256"
                             }
                          ],
                          "name":"tokenByIndex",
                          "outputs":[
                             {
                                "internalType":"uint256",
                                "name":"",
                                "type":"uint256"
                             }
                          ],
                          "stateMutability":"view",
                          "type":"function"
                       },
                       {
                          "inputs":[
                             {
                                "internalType":"address",
                                "name":"owner",
                                "type":"address"
                             },
                             {
                                "internalType":"uint256",
                                "name":"index",
                                "type":"uint256"
                             }
                          ],
                          "name":"tokenOfOwnerByIndex",
                          "outputs":[
                             {
                                "internalType":"uint256",
                                "name":"",
                                "type":"uint256"
                             }
                          ],
                          "stateMutability":"view",
                          "type":"function"
                       },
                       {
                          "inputs":[
                             {
                                "internalType":"uint256",
                                "name":"tokenId",
                                "type":"uint256"
                             }
                          ],
                          "name":"tokenURI",
                          "outputs":[
                             {
                                "internalType":"string",
                                "name":"",
                                "type":"string"
                             }
                          ],
                          "stateMutability":"view",
                          "type":"function"
                       },
                       {
                          "inputs":[

                          ],
                          "name":"totalSupply",
                          "outputs":[
                             {
                                "internalType":"uint256",
                                "name":"",
                                "type":"uint256"
                             }
                          ],
                          "stateMutability":"view",
                          "type":"function"
                       },
                       {
                          "inputs":[
                             {
                                "internalType":"address",
                                "name":"from",
                                "type":"address"
                             },
                             {
                                "internalType":"address",
                                "name":"to",
                                "type":"address"
                             },
                             {
                                "internalType":"uint256",
                                "name":"tokenId",
                                "type":"uint256"
                             }
                          ],
                          "name":"transferFrom",
                          "outputs":[

                          ],
                          "stateMutability":"nonpayable",
                          "type":"function"
                       }
                    ]

if __name__ == '__main__':
   erc = Erc721("", "ether", "testnet")
   erc.connect()
   print(erc.is_connected())
   print(erc.get_function())
   print(erc.deploy({'name': 'TEST'}))
