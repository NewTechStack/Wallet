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
                "mainnet": "https://polygon-rpc.com",
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
                self.contract_user = et_conn().db("wallet").table('contract_user')
                self.address_list = [account['address'] for account in list(self.accounts.with_fields('address').run())]
                self.contract_list = [contract['address'] for contract in list(self.contracts.with_fields('address').run())]
                break
            except:
                pass

    def check_address(self, link, address, chain_id):
        name = 'balanceOf'
        kwargs = {'account': address, 'owner': address}
        contracts = []
        for contract_address in self.contract_list:
            contract = list(self.contracts.filter(
                    (r.row['network'] == link[3])
                    & (r.row['network_type'] == link[2])
                    & (r.row["address"] == contract_address)
                ).run())
            if len(contract) == 0:
                continue
            contract = contract[0]
            abi = contract['deployment_infos']['abi']
            for function in abi:
                if 'type' in function and function['type'] == 'function':
                    if 'name' in function and function['name'] == name:
                        keep_function = function
            if keep_function is None:
                print(f"[{str(chain_id).ljust(10)}]: {address} : {contract_address}: Invalid function name")
                continue
            elem_kwargs = []
            for elem in keep_function['inputs']:
                elem_name = elem['name']
                elem_type = elem['type']
                elem_kwargs.append(elem['name'])
                if elem_name not in kwargs:
                    print(f"[{str(chain_id).ljust(10)}]: {address} : {contract_address}: Missing {elem_name}:{elem_type}")
                    continue
            contract = link[0].eth.contract(contract_address, abi=abi)
            transaction = contract.get_function_by_name(name)(**{name: kwargs[name] for name in elem_kwargs})
            tokens = transaction.call()
            if tokens == 0:
                print(f"[{str(chain_id).ljust(10)}]: {address} : {contract_address}: {tokens} tokens")
                contracts.append(
                        {
                            "id": contract['id'],
                            "address": contract_address,
                            "balance"
                        }
                    )
        data = {
            "network_type": link[2],
            "network": link[3],
            "account_addr": address,
            "contracts": contracts
        }
        ret = dict(self.contracts.filter(
                (r.row['network'] == link[3])
                & (r.row['network_type'] == link[2])
                & (r.row["account_addr"] == address)
            ).replace(data).run())
        print(ret)
        return [True]

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
                        chain_id = None
                        try:
                            chain_id = link[0].eth.chain_id
                        except:
                            pass
                        if chain_id is not None:
                            print(f"[{str(chain_id).ljust(10)}]: {address}")
                            ret = self.check_address(link, address, chain_id)
                            if ret[0] is True:
                                break
                        i += 1
                    if i == 3:
                        print(f'Passing: [{str(chain_id).ljust(10)}]: {address}')
                        continue
            print('Checked all address, sleeping ... ')
            time.sleep(30)
        return

if __name__ == '__main__':
   scroller = Scroller()
   scroller.start()
