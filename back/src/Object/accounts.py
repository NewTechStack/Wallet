from web3 import Web3
from web3.middleware import geth_poa_middleware
import json
from hexbytes import HexBytes

try:
    from .contracts import *
    from .rethink import get_conn, r
except:
    from contracts import *
    pass

class Account(W3):
    def __init__(self, usr_id = -1):
        super().__init__()
        self.connect()
        self.usr_id = str(usr_id)
        try:
            self.red = get_conn().db("wallet").table('accounts')
            self.trx = get_conn().db("wallet").table('transactions')
            self.ctr = get_conn().db("wallet").table('contracts')
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
                "creation_block": self.link.eth.get_block('latest')['number']
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

    def wallet_from_id(self, id):
        wallet = list(self.red.filter(
                (r.row["usr_id"] ==  self.usr_id)
                & (r.row["id"] ==  id)
            ).run())
        if len(wallet) == 0:
            return [False, "Invalid wallet id", 404]
        return [True, {'address': wallet[0]['address']}, None]

    def balance(self, id):
        account_addr = self.wallet_from_id(id)
        if account_addr[0] is False:
            return account_addr
        account_addr = account_addr[1]['address']
        balance = self.link.eth.get_balance(str(account_addr))
        return [True, {'data': balance}, None]

    def transactions(self, id):
        account_addr = self.wallet_from_id(id)
        if account_addr[0] is False:
            return account_addr
        account_addr = account_addr[1]['address']
        transactions = list(self.trx.filter(
                (r.row["address"] ==  account_addr)
                & (r.row["type"] ==  'account')
            ).run())
        return [True, {'data': transactions}, None]

    def token_balance(self, account_addr, contract_addr):
        contract_addr = self.link.toChecksumAddress(contract_addr)
        account_addr = self.__address_from_str(account_addr)
        if account_addr is False:
            return [False, "Invalid wallet ID - user correspondance checksumAddress", 404]
        contract = Erc20(contract_addr)
        balance = contract.functions.balanceOf(account_addr).call()
        return [True, {'contract_addr': balance}, None]

    def tokens(self, account_addr):
        print(list(self.ctr.run()))
        return [True, {}, None]

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

    def update_transac(self, address, since):
        actual = self.link.eth.get_block('latest')['number']
        while actual > since:
            block = self.link.eth.get_block(actual, full_transactions=True)
            for transaction in block['transactions']:
                recei = transaction['to']
                expe = transaction['from']
                if recei == address or expe == address:
                    print('found', transaction)
            actual -= 1
            print(actual)
        return

if __name__ == '__main__':
    account = Account()
    account.update_transac('0x781aD19FADc0482115D53ae660A76B852Ac8c276', 12)
