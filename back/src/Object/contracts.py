from web3 import Web3
from web3 import exceptions
from web3.middleware import geth_poa_middleware
import json

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
        gas_cost = cost + additionnal_gas
        gas_price = w3.toWei(10, 'gwei')
        ether_cost = Web3.fromWei(gas_price * gas_cost, 'ether')
        build = transaction.buildTransaction({
          'gas': gas_cost,
          'gasPrice': gas_price,
          'nonce': w3.eth.getTransactionCount(owner_address, "pending")
        })
        signed_txn = w3.eth.account.signTransaction(build, private_key=owner_key)
        txn = w3.eth.sendRawTransaction(signed_txn.rawTransaction).hex()
        w3.eth.waitForTransactionReceipt(txn)
        return [True, {"transact": txn, "cost": ether_cost}, None]

    def hextojson(self, data):
        class HexJsonEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, HexBytes):
                    return obj.hex()
                return super().default(obj)
        return json.loads(json.dumps(dict(data), cls=HexJsonEncoder))

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

    def deploy(self):
        owner = self.link.eth.account.from_mnemonic("quit comfort canal slam rare dynamic drift episode hen know sugar doctor")
        contract = self.link.eth.contract(abi=self.abi,bytecode=self.bytecode)
        transaction = contract.constructor()
        return self.execute_transaction(transaction, owner.address, owner.key)

    def is_compatible(self):
        contract = self.link.eth.contract(self.address, abi=self.abi)
        for func in self.abi:
            if func['type'] == 'function':
                exe = contract.get_function_by_name(func['name'])
                try:
                    args = [0]
                    exe(*args).call()
                except exceptions.ContractLogicError:
                    print('not comp')
                print('comp')
            return
            func_signature = Web3.eth.abi.encodeFunctionSignature(func)
            print(func['name'])
            print(func_signature)
            return

class Erc20(Contract):
    def __init__(self, address,  network_type = None, network = None):
         super().__init__(address, network_type = network_type, network = network)
         self.bytecode = ""
         self.abi = [
                       {
                          "inputs":[

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
                                "name":"spender",
                                "type":"address"
                             },
                             {
                                "indexed":False,
                                "internalType":"uint256",
                                "name":"value",
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
                                "indexed":False,
                                "internalType":"uint256",
                                "name":"value",
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
                                "name":"owner",
                                "type":"address"
                             },
                             {
                                "internalType":"address",
                                "name":"spender",
                                "type":"address"
                             }
                          ],
                          "name":"allowance",
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
                                "name":"spender",
                                "type":"address"
                             },
                             {
                                "internalType":"uint256",
                                "name":"amount",
                                "type":"uint256"
                             }
                          ],
                          "name":"approve",
                          "outputs":[
                             {
                                "internalType":"bool",
                                "name":"",
                                "type":"bool"
                             }
                          ],
                          "stateMutability":"nonpayable",
                          "type":"function"
                       },
                       {
                          "inputs":[
                             {
                                "internalType":"address",
                                "name":"account",
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
                          "name":"decimals",
                          "outputs":[
                             {
                                "internalType":"uint8",
                                "name":"",
                                "type":"uint8"
                             }
                          ],
                          "stateMutability":"view",
                          "type":"function"
                       },
                       {
                          "inputs":[
                             {
                                "internalType":"address",
                                "name":"spender",
                                "type":"address"
                             },
                             {
                                "internalType":"uint256",
                                "name":"subtractedValue",
                                "type":"uint256"
                             }
                          ],
                          "name":"decreaseAllowance",
                          "outputs":[
                             {
                                "internalType":"bool",
                                "name":"",
                                "type":"bool"
                             }
                          ],
                          "stateMutability":"nonpayable",
                          "type":"function"
                       },
                       {
                          "inputs":[
                             {
                                "internalType":"address",
                                "name":"spender",
                                "type":"address"
                             },
                             {
                                "internalType":"uint256",
                                "name":"addedValue",
                                "type":"uint256"
                             }
                          ],
                          "name":"increaseAllowance",
                          "outputs":[
                             {
                                "internalType":"bool",
                                "name":"",
                                "type":"bool"
                             }
                          ],
                          "stateMutability":"nonpayable",
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
                                "name":"recipient",
                                "type":"address"
                             },
                             {
                                "internalType":"uint256",
                                "name":"amount",
                                "type":"uint256"
                             }
                          ],
                          "name":"transfer",
                          "outputs":[
                             {
                                "internalType":"bool",
                                "name":"",
                                "type":"bool"
                             }
                          ],
                          "stateMutability":"nonpayable",
                          "type":"function"
                       },
                       {
                          "inputs":[
                             {
                                "internalType":"address",
                                "name":"sender",
                                "type":"address"
                             },
                             {
                                "internalType":"address",
                                "name":"recipient",
                                "type":"address"
                             },
                             {
                                "internalType":"uint256",
                                "name":"amount",
                                "type":"uint256"
                             }
                          ],
                          "name":"transferFrom",
                          "outputs":[
                             {
                                "internalType":"bool",
                                "name":"",
                                "type":"bool"
                             }
                          ],
                          "stateMutability":"nonpayable",
                          "type":"function"
                       }
                    ]


class Erc721(Contract):
    def __init__(self, address):
         super().__init__(address)
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
                    	}
                    ]

if __name__ == '__main__':
   erc = Erc20("", "ether", "testnet")
   erc.connect()
   print(erc.is_connected())
   print(erc.deploy())
