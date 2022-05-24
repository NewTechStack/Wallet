import time
import datetime
import json
from web3 import Web3
from web3 import exceptions
from hexbytes import HexBytes
from web3.middleware import geth_poa_middleware

from rethinkdb import RethinkDB

dbs = {"wallet": ["accounts", "contracts", "transactions", "transactions_meta", "contract_user"]}

def init():
    red = RethinkDB()
    for _ in range(10):
        try:
            red.connect("rethink", 28015, password="").repl()
            red.db_list().run()
            break
        except:
            continue
        time.sleep(2)
    if red is None:
        print("cannot connect to db")
        exit(1)
    else:
        db_list = red.db_list().run()
        if "test" in db_list:
            red.db_drop("test").run()
        for i in dbs:
            if i not in db_list:
                red.db_create(i).run()
            for j in dbs[i]:
                if j not in red.db(i).table_list().run():
                    red.db(i).table_create(j).run()
    return red

def get_conn():
    r = RethinkDB()
    r.connect("rethink", 28015, password="").repl()
    return r

init()
r = RethinkDB()

class Scroller:
    def __init__(self):
        self.w3 = {
            "polygon": {
                "mainnet": "https://polygon-r(pc.com",
                "testnet": "https://rpc-mumbai.matic.today"
            },
            "ether": {
                "testnet": "https://ropsten.infura.io/v3/9aa3d95b3bc440fa88ea12eaa4456161"
            }
        }
        self.c = []
        for w3 in self.w3:
            for link in self.w3[w3]:
                self.c.append((Web3(Web3.HTTPProvider(self.w3[w3][link])), self.w3[w3][link], w3, link))
        for link in self.c:
            link[0].middleware_onion.inject(geth_poa_middleware, layer=0)
        self.meta = None

    def init_db(self):
        while True:
            try:
                self.accounts = get_conn().db("wallet").table('accounts')
                self.contracts = get_conn().db("wallet").table('contracts')
                self.address_list = [account['address'] for account in list(self.accounts.with_fields('address').run())]
                self.contract_list = [contract['address'] for contract in list(self.contracts.with_fields('address').run())]
                break
            except:
                pass

    def check_address(self, link, address):
        for contract_address in self.contract_list:
            contract = list(self.contracts.filter((r.row["address"] == contract_address)).run())
            if len(contract) > 0:
                abi = contract[0]['deployment_infos']['abi']
            for function in abi:
                if 'type' in function and function['type'] == 'function':
                    if 'name' in function and function['name'] == name:
                        keep_function = function
            if keep_function is None:
                return [False, "Invalid function name"]
            elem_kwargs = []
            kwargs = {'account': address, 'owner': address}
            for elem in keep_function['inputs']:
                elem_name = elem['name']
                elem_type = elem['type']
                elem_kwargs.append(elem['name'])
                if elem_name not in kwargs:
                    return [False, f"missing {elem_name}:{elem_type}"]
            contract = link[0].eth.contract(contract_address, abi=abi)
            transaction = contract.get_function_by_name('balanceOf')(**{name: kwargs[name] for name in elem_kwargs})
            return [True, transaction.call()]

    def start(self):
        loop_number = 0
        while True:
            loop_number = loop_number + 1 if loop_number < 99999 else 1
            print('Connection to Database')
            self.init_db()
            print('Connected to Database')
            print(f"Starting loop {str(loop_number).rjust(5, '0')}")
            for address in self.address_list:
                for link in self.c:
                    i = 0
                    while True and i < 3:
                        # try:
                        chain_id = link[0].eth.chain_id
                        ret = check_address(link, address)
                        print(ret)
                        if ret[0] is True:
                            break
                        # except:
                        #     pass
                        i += 1
                    if i == 3:
                        print(f'Passing: [{str(chain_id).ljust(10)}]: {address}')
                        continue
                    print(f"[{str(chain_id).ljust(10)}]: {address}")
            print('Checked all address, sleeping ... ')
            time.sleep(30)
        return

if __name__ == '__main__':
   scroller = Scroller()
   scroller.start()
