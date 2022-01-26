from Model.sso import *
from Model.accounts import *

def setuproute(app, call):
    @app.route('/',                                     ['OPTIONS', 'GET'],           lambda x = None: call([])) #done
    @app.route('/sso',                                  ['OPTIONS', 'GET'],           lambda x = None: call([sso_url])                                           )
    @app.route('/sso/conn/<>',                          ['OPTIONS', 'GET'],           lambda x = None: call([sso_token])                                         )

    @app.route('/chain',                                ['OPTIONS', 'GET'],           lambda x = None: call([sso_verify_token, account_load, blockcahin_status])  )
    @app.route('/chain/wallet',                         ['OPTIONS', 'POST'],          lambda x = None: call([sso_verify_token, account_load, account_create])  )
    @app.route('/chain/wallets',                        ['OPTIONS', 'GET'],           lambda x = None: call([sso_verify_token, account_load, account_all])  )
    @app.route('/chain/wallet/<>/balance',              ['OPTIONS', 'GET'],           lambda x = None: call([sso_verify_token, account_load, account_balance])  )
    @app.route('/contract/<>/constructor',              ['OPTIONS', 'GET'],           lambda x = None: call([contract_type, contract_get_constructor])  )
    @app.route('/contract/<>/deploy',                   ['OPTIONS', 'POST'],          lambda x = None: call([contract_type, contract_exec_constructor])  )
    @app.route('/contract/<>/<>/functions',             ['OPTIONS', 'GET'],           lambda x = None: call([sso_verify_token, contract_type, contract_get_function])  )
    @app.route('/contract/<>/<>/<>',                    ['OPTIONS', 'POST'],          lambda x = None: call([sso_verify_token, contract_type, contract_exec_function])  )
    def base():
        return
