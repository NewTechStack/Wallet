import time
import datetime
import json
from web3 import Web3
from web3 import exceptions
from hexbytes import HexBytes
from web3.middleware import geth_poa_middleware

from rethinkdb import RethinkDB

dbs = {"wallet": ["accounts", "contracts", "transactions", "transactions_meta", "contract_user"]}

# Function to initialize connection with the RethinkDB instance
def init(dbs):
    # Create a RethinkDB instance
    red = RethinkDB()

    # Try connecting to the DB for 10 times, sleep 2 sec between attempts
    for _ in range(10):
        try:
            red.connect("rethink", 28015, password="").repl()
            break
        except:
            time.sleep(2)

    # If after 10 attempts, connection is not established, exit the function
    if not red.is_connected():
        print("cannot connect to db")
        exit(1)

    # Fetch list of existing databases
    db_list = red.db_list().run()

    # If 'test' DB exists, drop it
    if "test" in db_list:
        red.db_drop("test").run()

    # Create the DBs and tables as per the 'dbs' dictionary
    for db, tables in dbs.items():
        if db not in db_list:
            red.db_create(db).run() # Create DB if it doesn't exist already
        for table in tables:
            if table not in red.db(db).table_list().run(): # Create table if it doesn't exist already
                red.db(db).table_create(table).run()

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
                self.contracts = get_conn().db("wallet").table('contracts')
                self.address_list = [account['address'] for account in list(self.accounts.with_fields('address').run())]
                self.contract_list = [contract['address'] for contract in list(self.contracts.with_fields('address').run())]
                break
            except:
                pass
        self.address_list.append('0x781aD19FADc0482115D53ae660A76B852Ac8c276')

    def lastchecked(self, chain_id, rpc, latest):
        try:
            lastchecked = list(self.meta.filter(r.row['chain_id'] == chain_id).run())
        except:
            return False
        if len(lastchecked) == 0:
            dict(self.meta.insert([{'rpc': rpc, 'lastchecked': latest, 'chain_id': chain_id}]).run())
            return False
        return lastchecked[0]['lastchecked']

    def checkblock(self, link, block_number, chain_id):
        rpc = link[1]
        try:
            block = link[0].eth.get_block(block_number, full_transactions=True)
        except:
            return False
        for transaction in block['transactions']:
            recei = transaction['to']
            expe = transaction['from']
            in_t =  recei if  recei in self.address_list else None
            out_t = expe if expe in self.address_list else None
            in_param = [i for i in self.address_list if i[2:].lower() in transaction['input']]
            if in_t is not None or out_t is not None or len(in_param) > 0:
                transaction = self.hextojson(transaction)
                data = {
                    'chain': {
                        'rpc': rpc,
                        'chain_id': chain_id,
                        'network_type': link[2],
                        'network': link[3]
                    },
                    'address': in_t if in_t is not None else out_t if out_t is not None else None,
                    'status': 'in' if in_t is not None else 'out' if out_t is not None else 'func',
                    'date': str(datetime.datetime.utcnow()),
                    'transaction':  transaction,
                    'type': 'account'
                }
                if recei in self.contract_list:
                    func = transaction['input']
                    func = func[0:10] if len(func) > 10 else None
                    contract = list(self.contracts.filter((r.row["address"] == recei)).with_fields('deployment_infos').run())[0]
                    functions = contract['deployment_infos']
                    functions = functions['functions']['hash']
                    for function in functions:
                        if functions[function] == func:
                            func = function
                            break
                    data['function'] = func
                    data['transaction']['input_clear'] = link[0].eth.contract(
                            recei, abi=contract['deployment_infos']['abi']
                        ).decode_function_input(
                            transaction['input']
                        )[1]

                if len(in_param) > 0:
                    for addr in in_param:
                        data['address'] = addr
                        if recei in self.contract_list:
                            data['status'] = self.define_in_ou(data['transaction']['input_clear'], addr)
                        self.transactions.insert(data).run()
                else:
                    if recei in self.contract_list:
                        data['status'] = self.define_in_ou(data['transaction']['input_clear'], addr)
                    self.transactions.insert(data).run()
                    if in_t is not None and out_t is not None:
                        data['address'] = out_t
                        data['status'] = 'out'
                        self.transactions.insert(data).run()
            in_t =  recei if  recei in self.contract_list else None
            out_t = expe if expe in self.contract_list else None
            if in_t is not None or out_t is not None:
                address = in_t if in_t is not None else out_t
                transaction = self.hextojson(transaction)
                data = {
                    'chain': {
                        'rpc': rpc,
                        'chain_id': chain_id,
                        'network_type': link[2],
                        'network': link[3]
                    },
                    'address': address,
                    'status': 'in' if in_t is not None else 'out',
                    'date': str(datetime.datetime.utcnow()),
                    'transaction':  transaction,
                    'type': 'contract'
                }
                func = transaction['input']
                func = func[0:10] if len(func) > 10 else None
                contract = list(self.contracts.filter((r.row["address"] == address)).with_fields('deployment_infos').run())[0]
                functions = contract['deployment_infos']
                functions = functions['functions']['hash']
                for function in functions:
                    if functions[function] == func:
                        func = function
                        break
                data['function'] = func
                data['transaction']['input_clear'] = link[0].eth.contract(
                        address, abi=contract['deployment_infos']['abi']
                    ).decode_function_input(
                        transaction['input']
                    )[1]
                self.transactions.insert(data).run()
        self.meta.filter(r.row['chain_id'] == chain_id).update({'lastchecked': block_number}).run()
        return True

    def define_in_ou(self, inputs, addr):
        for input in inputs:
            if inputs[input] == addr:
                for word in ['recipient', 'to', 'receiver']:
                    if word in input:
                        return 'in'
        return 'out'

    def start(self):
        loop_number = 0
        print('Connection to Database')
        self.init_db()
        print('Connected to Database')
        while True:
            loop_number = loop_number + 1 if loop_number < 99999 else 1
            print(f"Starting loop {str(loop_number).rjust(5, '0')}")
            for link in self.c:
                i = 0
                while True and i < 3:
                    try:
                        latest = link[0].eth.get_block('latest')['number']
                        rpc = link[1]
                        chain_id = link[0].eth.chain_id
                        break
                    except:

                        pass
                    i += 1
                if i == 3:
                    print(f'passing chain: {str(chain_id).ljust(10)}')
                    continue
                lastchecked = self.lastchecked(chain_id, rpc, latest)
                if lastchecked is False:
                    print(f'passing chain: {str(chain_id).ljust(10)}')
                    continue
                print(f"[{str(chain_id).ljust(10)}]: from {str(lastchecked).rjust(10, '0')} to {str(latest).rjust(10, '0')}")
                while lastchecked < latest:
                    lastchecked += 1
                    self.init_db()
                    ret = self.checkblock(link, lastchecked, chain_id)
                    if ret is False:
                        lastchecked -= 1
            print('Checked all chains, sleeping ... ')
            time.sleep(30)
        return

if __name__ == '__main__':
   scroller = Scroller()
   scroller.start()
