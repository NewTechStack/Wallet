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

    def hextojson(self, data):
        class HexJsonEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, HexBytes):
                    return obj.hex()
                if isinstance(obj, decimal.Decimal):
                    return float(obj)
                return super().default(obj)
        return json.loads(json.dumps(dict(data), cls=HexJsonEncoder))

    def init_db(self):
        while True:
            try:
                self.meta = get_conn().db("wallet").table('transactions_meta')
                self.transactions = get_conn().db("wallet").table('transactions')
                self.accounts = get_conn().db("wallet").table('accounts')
                self.address_list = [account['address'] for account in list(self.accounts.run())]
                break
                print('waiting for DB')
            except:
                pass
        self.address_list.append('0x781aD19FADc0482115D53ae660A76B852Ac8c276')
        print(self.address_list)

    def lastchecked(self, network):
        try:
            lastchecked = list(self.meta.filter(r.row['network'] == network).run())
        except:
            return False
        if len(lastchecked) == 0:
            dict(self.meta.insert([{'network': network, 'lastchecked': latest}]).run())
            return False
        return lastchecked[0]['lastchecked']

    def checkblock(self, link, block_number,  network):
        block = link[0].eth.get_block(block_number, full_transactions=True)
        for transaction in block['transactions']:
            recei = transaction['to']
            expe = transaction['from']
            address =  recei if  recei in self.address_list else None
            address = expe if expe in self.address_list else None
            if address is not None :
                self.transactions.insert({
                    'chain': link[1],
                    'address': address,
                    'date': str(datetime.datetime.utcnow()),
                    'transaction':  transaction,
                    'type': 'account'
                }).run()
        self.meta.filter(r.row['network'] == link[1]).update({'lastchecked': latest}).run()

    def start(self):
        self.init_db()
        while True:
            for link in self.c:
                latest = link[0].eth.get_block('latest')['number']
                network = link[1]
                lastchecked = self.lastchecked(network)
                if lastchecked is False:
                    continue
                print(f"{network.ljust(25)}: from {str(lastchecked).ljust(10)} to {str(latest).ljust(10)}")
                while lastchecked < latest:
                    lastchecked += 1
                    self.checkblock(link, network)
            time.sleep(30)
        return

if __name__ == '__main__':
   scroller = Scroller()
   scroller.start()
