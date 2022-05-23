from web3 import Web3
from web3.middleware import geth_poa_middleware
import json
import math
from hexbytes import HexBytes
import datetime

try:
    from .contracts import *
    from .rethink import get_conn, r
except:
    from contracts import *
    pass

class Account(W3):
    def __init__(self, usr_id = -1, network_type = None, network = None):
        super().__init__(network_type = network_type, network = network)
        self.connect()
        self.usr_id = str(usr_id)
        try:
            self.red = get_conn().db("wallet").table('accounts')
            self.trx = get_conn().db("wallet").table('transactions')
            self.ctr = get_conn().db("wallet").table('contracts')
        except:
            self.red = None

    def create(self, name, usr_id = None):
        usr_id = usr_id if usr_id is not None else self.usr_id
        if usr_id == "-1" or usr_id is None:
            return [False, "", 400]
        acct, mnem = self.link.eth.account.create_with_mnemonic()
        data = {
                "usr_id": usr_id,
                "name": name,
                "address": str(acct.address),
                "mnemonic": str(mnem),
                "key": str(acct.key),
                "date": str(datetime.datetime.utcnow())
        }
        res = dict(self.red.insert([data]).run())
        id = res["generated_keys"][0]
        return [True, {"id": id, "address": str(acct.address), "mnemonic": str(mnem)} , None]

    def get_all(self, usr_id = None, anon = True):
        usr_id = usr_id if usr_id is not None else self.usr_id
        wallets = list(self.red.filter(
                (r.row["usr_id"] == usr_id)
            ).run())
        i = 0
        if len(wallets) == 0:
            self.create('base', usr_id)
            return self.get_all(usr_id, anon=anon)
        if anon is True:
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
        return [True, {'data': balance, "unit": self.unit}, None]

    def transactions(self, id, contract, page = 1, bypage = 1000):
        page = int(page)
        bypage = int(bypage)
        page = (page if page > 0 else 0)
        bypage = (bypage if bypage > 5 else 5)
        start = page * bypage
        end = (page + 1) * bypage
        account_addr = self.wallet_from_id(id)
        if account_addr[0] is False:
            return account_addr
        account_addr = account_addr[1]['address']
        transactions = self.trx.filter(
                (r.row["address"] ==  account_addr)
                & (r.row["type"] == 'account')
                & (r.row["chain"]["network_type"] == self.network_type)
                & (r.row["chain"]["network"] == self.network)
            )
        if contract is not None:
            transactions = transactions.filter(
                    (r.row["transaction"]["to"] == contract)
                )
        ret = list(transactions.order_by(r.desc(r.row['date'])).slice(start, end).run())
        in_search = int(transactions.count().run())
        pagination = { "actual": page, "min": 0, "max": int(math.ceil(in_search / bypage)) - 1 }
        if pagination['actual'] > pagination['max']:
            return [False, "Over pagination", 404]
        resume = {"in_search": in_search, "page": pagination}
        return [True, {"transaction": ret, "pagination": resume}, None]

    def token_balance(self, account_addr, contract_addr):
        contract_addr = self.link.toChecksumAddress(contract_addr)
        account_addr = self.__address_from_str(account_addr)
        if account_addr is False:
            return [False, "Invalid wallet ID - user correspondance checksumAddress", 404]
        contract = Erc20(contract_addr)
        balance = contract.functions.balanceOf(account_addr).call()
        return [True, {'contract_addr': balance}, None]

    def tokens(self, account_addr):
        account_addr = self.link.toChecksumAddress(account_addr)
        contracts = list(self.ctr.filter(
            (r.row["network_type"] == self.network_type)
            & (r.row["network"] == self.network)
            ).run())
        ret = {}
        for contract in contracts:
            c = Contract('', self.network_type, self.network).internal_get_contract(contract['id'])[1]
            c.connect()
            args = {'account': account_addr, 'owner': account_addr}
            res = c.exec_function('balanceOf', args)
            if res[1]['result'] > 0:
                ret[contract['id']] = {'address': contract['address'], 'balance': res[1]['result']}
        return [True, ret, None]

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

if __name__ == '__main__':
    account = Account()
