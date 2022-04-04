from Model.sso import *
from Model.accounts import *

def setuproute(app, call):
    @app.route('/',                                     ['OPTIONS', 'GET'],           lambda x = None: call([])) #done
    @app.route('/sso',                                  ['OPTIONS', 'GET'],           lambda x = None: call([sso_url])                                           )
    @app.route('/sso/conn/<>',                          ['OPTIONS', 'GET'],           lambda x = None: call([sso_token])                                         )
    @app.route('/sso/user',                             ['OPTIONS', 'POST'],          lambda x = None: call([sso_verify_token, sso_user_by_email])                                 )

    @app.route('/chain',                                ['OPTIONS', 'GET'],           lambda x = None: call([sso_verify_token, account_load, blockchain_status])  )
    @app.route('/wallet',                               ['OPTIONS', 'POST'],          lambda x = None: call([sso_verify_token, account_load, account_create])  )
    @app.route('/wallets',                              ['OPTIONS', 'GET'],           lambda x = None: call([sso_verify_token, account_load, account_all])  )
    @app.route('/wallet/<>/balance',                    ['OPTIONS', 'GET'],           lambda x = None: call([sso_verify_token, account_load, account_balance])  )
    @app.route('/wallet/<>/transactions',               ['OPTIONS', 'GET'],           lambda x = None: call([sso_verify_token, account_load, account_transactions])  )
    @app.route('/contract',                             ['OPTIONS', 'GET'],           lambda x = None: call([sso_verify_token, contract])  )
    @app.route('/contract/<>/constructor',              ['OPTIONS', 'GET'],           lambda x = None: call([sso_verify_token, contract_by_type, contract_get_constructor])  )
    @app.route('/contract/<>/deploy',                   ['OPTIONS', 'POST'],          lambda x = None: call([sso_verify_token, contract_by_type, contract_exec_constructor])  )
    @app.route('/contract/<>/functions',                ['OPTIONS', 'GET'],           lambda x = None: call([sso_verify_token, contract_by_id, contract_get_function])  )
    @app.route('/contract/<>/transactions',             ['OPTIONS', 'GET'],           lambda x = None: call([sso_verify_token, contract_by_id, contract_get_transaction])  )
    @app.route('/contract/<>/<>',                       ['OPTIONS', 'POST'],          lambda x = None: call([sso_verify_token, contract_by_id, contract_exec_function])  )
    @app.route('/user/wallets',                      ['OPTIONS', 'POST'],           lambda x = None: call([sso_verify_token, account_by_user]))
    def base():
        return
