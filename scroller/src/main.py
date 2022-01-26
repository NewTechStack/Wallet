import time
from web3 import Web3
from web3 import exceptions
from web3.middleware import geth_poa_middleware

from rethinkdb import RethinkDB

dbs = {"wallet": ["accounts", "contracts", "transactions", "transactions_meta"]}

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
                self.c.append((Web3(Web3.HTTPProvider(self.w3[w3][link])), self.w3[w3][link]))
        for link in self.c:
            link[0].middleware_onion.inject(geth_poa_middleware, layer=0)

    def start(self):
        while True:
            if True:
                self.meta = get_conn().db("wallet").table('transactions_meta')
                self.transactions = get_conn().db("wallet").table('transactions')
                break
                print('waiting for DB')
        while True:
            for link in self.c:
                latest = link[0].eth.get_block('latest')['number']
                network = link[1]
                lastchecked = list(self.meta.filter(r.row['network'] == network).run())
                if len(lastchecked) == 0:
                    res = dict(self.meta.insert([{'network': network, 'lastchecked': latest}]).run())
                else:
                    lastchecked = lastchecked[0]['lastchecked']
                    print(f"{network}: from {lastchecked} to {latest}")
                    while lastchecked < latest:
                        lastchecked += 1
                        self.meta.filter(r.row['network'] == link[1]).update({'lastchecked': latest}).run()
            time.sleep(30)
        return

if __name__ == '__main__':
   scroller = Scroller()
   scroller.start()
