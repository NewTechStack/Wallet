from web3 import Web3
from web3.middleware import geth_poa_middleware
import json
from hexbytes import HexBytes
from .contracts import *
try:
    from .rethink import get_conn, r
except:
    pass

class Account(W3):
    def __init__(self, usr_id = -1):
        super().__init__()
        self.connect()
        self.usr_id = str(usr_id)
        try:
            self.red = get_conn().db("wallet").table('accounts')
        except:
            self.red = None

    def create(self, name):
        if self.usr_id == "-1":
            return [False, "", 400]
        acct, mnem = self.link.eth.account.create_with_mnemonic()
        data = {
                "usr_id": self.usr_id,
                "name": name,
                "address": str(acct.address),
                "mnemonic": str(mnem),
                "key": str(acct.key),
                "creation_block": self.link.eth.get_block('latest')['number'],
                "transactions": {
                  "last_checked": self.link.eth.get_block('latest')['number'],
                  "transactions_details": []
                }
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
            del wallets[i]['key']
            i += 1
        return [True, {'wallets': wallets}, None]

    def balance(self, account_addr):
        account_addr = self.__address_from_str(account_addr)
        if account_addr is False:
            return [False, "Invalid wallet ID - user correspondance checksumAddress", 404]
        balance = self.link.eth.get_balance(str(account_addr))
        return [True, {'data': balance}, None]

    def token_balance(self, account_addr, contract_addr):
        contract_addr = self.link.toChecksumAddress(contract_addr)
        account_addr = self.__address_from_str(account_addr)
        if account_addr is False:
            return [False, "Invalid wallet ID - user correspondance checksumAddress", 404]
        contract = Erc20(contract_addr)
        balance = contract.functions.balanceOf(account_addr).call()
        return [True, {'contract_addr': balance}, None]

    def __address_from_id(self, wallet_id):
        wallets = list(self.red.filter(
                (r.row["usr_id"] == self.usr_id)
                & (r.row["id"] == wallet_id)
            ).run())
        if len(wallets) != 1:
            return False
        return wallets[0]['address']

    def __address_from_str(self, data):
        wallet = self.__address_from_id(data)
        if wallet is not False:
            return wallet
        try:
            return self.link.toChecksumAddress(data)
        except:
            pass
        return False
