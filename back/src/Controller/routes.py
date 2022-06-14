from Model.sso import *
from Model.accounts import *

def setuproute(app, call):
    @app.route('/',                                     ['OPTIONS', 'GET'],           lambda x = None: call([])) #done
    @app.route('/sso',                                  ['OPTIONS', 'GET'],           lambda x = None: call([sso_url])                                           )
    @app.route('/sso/conn/<>',                          ['OPTIONS', 'GET'],           lambda x = None: call([sso_token])                                         )
    @app.route('/sso/user',                             ['OPTIONS', 'POST'],          lambda x = None: call([sso_verify_token, sso_user_by_email])               )

    @app.route('/chain',                                ['OPTIONS', 'GET'],           lambda x = None: call([sso_verify_token, chains])  )
    @app.route('/chain/<>/<>',                          ['OPTIONS', 'GET'],           lambda x = None: call([sso_verify_token, account_load, blockchain_status])  )
    # @app.route('/wallet',                               ['OPTIONS', 'POST'],          lambda x = None: call([sso_verify_token, account_load, account_create])  )
    @app.route('/wallets',                              ['OPTIONS', 'GET'],           lambda x = None: call([sso_verify_token, account_load, account_all])  )
    @app.route('/chain/<>/<>/wallet/<>/balance',        ['OPTIONS', 'GET'],           lambda x = None: call([sso_verify_token, load_network, account_load, account_balance])  )
    @app.route('/chain/<>/<>/wallet/<>/transactions',   ['OPTIONS', 'GET'],           lambda x = None: call([sso_verify_token, load_network, account_load, account_transactions])  )
    @app.route('/chain/<>/<>/wallet/<>/contracts',      ['OPTIONS', 'GET'],           lambda x = None: call([sso_verify_token, load_network, account_load,  account_tokens])  )
    @app.route('/chain/<>/<>/contract',                 ['OPTIONS', 'GET'],           lambda x = None: call([sso_verify_token, load_network, contract])  )
    @app.route('/chain/<>/<>/contract/<>/constructor',  ['OPTIONS', 'GET'],           lambda x = None: call([sso_verify_token, load_network, contract_by_type, contract_get_constructor])  )
    @app.route('/chain/<>/<>/contract/<>/deploy',       ['OPTIONS', 'POST'],          lambda x = None: call([sso_verify_token, load_network, contract_by_type, contract_exec_constructor])  )
    @app.route('/chain/<>/<>/contract/<>/deploy/cmd',   ['OPTIONS', 'POST'],          lambda x = None: call([sso_verify_token, load_network, account_load, contract_by_type, contract_exec_constructor, email_to_address, contract_cmd])  )
    @app.route('/chain/<>/<>/contract/<>/cmd',          ['OPTIONS', 'POST'],          lambda x = None: call([sso_verify_token, load_network, account_load, contract_by_id, email_to_address, contract_cmd])  )
    @app.route('/chain/<>/<>/contract/<>/functions',    ['OPTIONS', 'GET'],           lambda x = None: call([sso_verify_token, load_network, contract_by_id, email_to_address, contract_cmd])  )
    @app.route('/chain/<>/<>/contract/<>/transactions', ['OPTIONS', 'GET'],           lambda x = None: call([sso_verify_token, load_network, contract_by_id, contract_get_transaction])  )
    @app.route('/chain/<>/<>/contract/<>/<>',           ['OPTIONS', 'POST'],          lambda x = None: call([sso_verify_token, load_network, account_load, contract_by_id, email_to_address, contract_exec_function])  )
    @app.route('/contract/<>',                          ['OPTIONS', 'DELETE'],        lambda x = None: call([sso_verify_token, contract_delete_by_id])  )
    @app.route('/user/wallets',                         ['OPTIONS', 'POST'],          lambda x = None: call([account_by_user]))
    def base():
        return
