from web3 import Web3
from web3.middleware import geth_poa_middleware
import json
from hexbytes import HexBytes

class HexJsonEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, HexBytes):
            return obj.hex()
        return super().default(obj)

try:
    from .rethink import get_conn, r
except:
    pass

class Account:
    def __init__(self, usr_id = -1):
        self.w3 = Web3(Web3.HTTPProvider('https://rpc-mumbai.matic.today'))
        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        self.usr_id = str(usr_id)
        try:
            self.red = get_conn().db("wallet").table('accounts')
        except:
            self.red = None

    def status(self):
        block = self.w3.eth.get_block('latest')
        ret = json.dumps(dict(block), cls=HexJsonEncoder)
        return [True, {'data': json.loads(ret)}, None]

    def create(self, name):
        if self.usr_id == "-1":
            return [False, "", 400]
        self.w3.eth.account.enable_unaudited_hdwallet_features()
        acct, mnem = self.w3.eth.account.create_with_mnemonic()
        data = {
                "usr_id": self.usr_id,
                "name": name,
                "address": str(acct.address),
                "mnemonic": str(mnem)
        }
        res = dict(self.red.insert([data]).run())
        id = res["generated_keys"][0]
        return [True, {"id": id, "address": str(acct.address), "mnemonic": str(mnem)} , None]

    def get_all(self):
        wallets = list(self.red.filter(
                (r.row["usr_id"] ==  self.usr_id)
            ).run())
        i = 0
        while i < len(wallets):
            del wallets[i]['mnemonic']
            i += 1
        return [True, {'wallets': wallets}, None]

    def balance(self, account_addr):
        account_addr = self.__address_from_str(account_addr)
        if account_addr is False:
            return [False, "Invalid wallet ID - user correspondance checksumAddress", 404]
        return [True, {'data': self.web3.eth.get_balance(str(addr))}, None]

    def token_balance(self, account_addr, contract_addr):
        contract_addr = self.w3.toChecksumAddress(contract_addr)
        account_addr = self.__address_from_str(account_addr)
        if account_addr is False:
            return [False, "Invalid wallet ID - user correspondance checksumAddress", 404]
        minABI = [
          {
            "constant": True,
            "inputs":[{"name":"_owner","type":"address"}],
            "name":"balanceOf",
            "outputs":[{"name":"balance","type":"uint256"}],
            "type":"function"
          },
          {
            "constant": True,
            "inputs":[],
            "name":"decimals",
            "outputs":[{"name":"","type":"uint8"}],
            "type":"function"
          }
        ]
        contract = self.w3.eth.contract(contract_addr, abi=minABI)
        balance = contract.functions.balanceOf(account_addr).call()
        return [True, {contract_addr: balance}, None]

    def __is_connected(self):
        return self.w3.isConnected()

    def __address_from_id(self, wallet_id):
        wallets = list(self.red.filter(
                (r.row["usr_id"] == self.usr_id)
                & (r.row["id"] == wallet_id)
            ).run())
        if len(wallet) != 1:
            return False
        return wallets[0]['address']

    def __address_from_str(self, data):
        wallet = self.__address_from_id(data)
        if wallet is not False:
            return wallet
        try:
            return self.w3.toChecksumAddress(data)
        except:
            pass
        return False
