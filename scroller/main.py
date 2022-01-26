import time
from web3 import Web3
from web3 import exceptions
from web3.middleware import geth_poa_middleware

from rethinkdb import RethinkDB

def get_conn():
    r = RethinkDB()
    r.connect("rethink", 28015, password="").repl()
    return r

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
        self.meta = get_conn().db("wallet").table('transactions_meta')
        self.transactions = get_conn().db("wallet").table('transactions')

    def start(self):
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
