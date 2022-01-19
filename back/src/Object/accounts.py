from web3 import Web3
try:
    from .rethink import get_conn, r
except:
    pass

class Account:
    def __init__(self, usr_id = -1):
        self.w3 = Web3(Web3.HTTPProvider('https://rpc-mumbai.matic.today'))
        self.usr_id = str(usr_id)
        try:
            self.red = get_conn().db("sell")
        except:
            self.red = None

    def status(self):
        return [True, {'data': w3.eth.get_block('latest')}, None]

    def create(self, name):
        if usr_id == "-1":
            return [False, "", 400]
        acct, mnem = w3.eth.account.create_with_mnemonic()
        data = {
                "usr_id": self.usr_id,
                "address": str(acct.address),
                "mnemonic": str(mnem)
        }
        res = dict(self.red.insert([data]).run())
        id = res["generated_keys"][0] if id is None else id
        return [True, {"id": id, "address": str(acct.address), "mnemonic": str(mnem)} , None]

    def get_all(self):
        wallets = list(self.red.filter(
                (r.row["usr_id"] ==  self.usr_id)
            ).run())
        return [True, {'wallets': wallets}, None]

    def balance(self, account_addr):
        account_addr = w3.toChecksumAddress(account_addr)
        return [True, {'data': web3.eth.get_balance(str(addr))}, None]

    def token_balance(self, account_addr, contract_addr):
        contract_addr = w3.toChecksumAddress(contract_addr)
        account_addr = w3.toChecksumAddress(account_addr)
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
        ];
        contract = w3.eth.contract(contract_addr, abi=minABI)
        balance = contract.functions.balanceOf(account_addr).call()
        return [True, {contract_addr: balance}, None]

    def __is_connected(self):
        return w3.isConnected()
