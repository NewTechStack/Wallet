from Controller.basic import check
from Object.utils import Utils
from Object.accounts import Account
from Object.contracts import *

def chains(cn, nextc):
    err = [True, W3().networks, None]
    return cn.call_next(nextc, err)

def load_network(cn, nextc):
    err = check.contain(cn.rt, ["chain"])
    if not err[0]:
        return cn.toret.add_error(err[1], err[2])
    err = check.contain(cn.rt, [cn.rt["chain"]])
    if not err[0]:
        return cn.toret.add_error(err[1], err[2])
    cn.private['network_type'] = cn.rt['chain']
    cn.private['network'] = cn.rt[cn.rt["chain"]]
    err = [True, {}, None]
    return cn.call_next(nextc, err)

def account_load(cn, nextc):
    usr_id = None
    if 'sso' in cn.private:
        usr_id = cn.private["sso"].user["id"]
    cn.private["account"] = Account(usr_id,
        cn.private['network_type'] if 'network_type' in cn.private else None,
        cn.private['network'] if 'network' in cn.private else None
    )
    err = [True, {}, None]
    return cn.call_next(nextc, err)

def blockchain_status(cn, nextc):
    err = cn.private["account"].status()
    return cn.call_next(nextc, err)

def account_by_user(cn, nextc):
    err = check.contain(cn.pr, ["email"])
    if not err[0]:
        return cn.toret.add_error(err[1], err[2])
    err = cn.private["sso"].user_by_email(cn.pr['email'])
    Acc = Account(err[1]['id'])
    wallets = Acc.get_all()[1]['wallets']
    if len(wallets) == 0:
        Acc.create('Base')
    err = Acc.get_all()
    return cn.call_next(nextc, err)

def account_create(cn, nextc):
    err = check.contain(cn.pr, ["name"])
    if not err[0]:
        return cn.toret.add_error(err[1], err[2])
    err = cn.private["account"].create(cn.pr["name"])
    return cn.call_next(nextc, err)

def account_all(cn, nextc):
    err = cn.private["account"].get_all()
    return cn.call_next(nextc, err)

def account_balance(cn, nextc):
    err = check.contain(cn.rt, ["wallet"])
    if not err[0]:
        return cn.toret.add_error(err[1], err[2])
    err = cn.private["account"].balance(cn.rt["wallet"])
    return cn.call_next(nextc, err)

def account_transactions(cn, nextc):
    contract = cn.get["contract"] if "contract" in cn.get else None
    page = cn.get["page"] if "page" in cn.get else 0
    bypage = cn.get["bypage"] if "bypage" in cn.get else 1000
    err = check.contain(cn.rt, ["wallet"])
    if not err[0]:
        return cn.toret.add_error(err[1], err[2])
    err = cn.private["account"].transactions(cn.rt["wallet"], contract, page, bypage)
    return cn.call_next(nextc, err)

def account_tokens(cn, nextc):
    err = check.contain(cn.rt, ["wallet"])
    if not err[0]:
        return cn.toret.add_error(err[1], err[2])
    err = cn.private["account"].tokens(cn.rt["wallet"])
    return cn.call_next(nextc, err)

def contract_by_type(cn, nextc):
    err = check.contain(cn.rt, ["contract"])
    if not err[0]:
        return cn.toret.add_error(err[1], err[2])
    contracts = {
        "ERC20": Erc20,
        "ERC721": Erc721
    }
    if cn.rt['contract'] not in contracts:
        return cn.toret.add_error('Invalid contract type', 400)
    contract_type = contracts[cn.rt['contract']]
    contract_address = cn.rt[cn.rt['contract']] if cn.rt['contract'] in cn.rt else ''
    if not err[0]:
        return cn.toret.add_error(err[1], err[2])
    cn.private['contract'] = contract_type(contract_address)
    cn.private['contract'].connect()
    err = [True, {}, None]
    return cn.call_next(nextc, err)

def contract_by_id(cn, nextc):
    contract = str(cn.rt.get('contract'))
    err = Contract(' ', cn.private['network_type'], cn.private['network']).internal_get_contract(contract)
    if not err[0]:
        return cn.toret.add_error(err[1], err[2])
    cn.private['contract'] = err[1]
    cn.private['contract'].connect()
    err = [True, {}, None]
    return cn.call_next(nextc, err)

def contract_get_function(cn, nextc):
    contract = str(cn.rt.get('contract'))
    err = cn.private['contract'].get_functions(contract)
    return cn.call_next(nextc, err)

def contract_exec_constructor(cn, nextc):
    err = check.contain(cn.pr, ["kwargs", "metadata"])
    if not err[0]:
        return cn.toret.add_error(err[1], err[2])
    err = cn.private['contract'].deploy(cn.pr["kwargs"], cn.pr["metadata"])
    if err[0]:
        err = Contract(' ', cn.private['network_type'], cn.private['network']).internal_get_contract(err[1]['id'])
        cn.private['contract'] = err[1]
        cn.private['contract'].connect()
    return cn.call_next(nextc, err)

def contract_get_constructor(cn, nextc):
    err = cn.private['contract'].get_constructor()
    return cn.call_next(nextc, err)

def contract_get_transaction(cn, nextc):
    contract = cn.rt['contract']
    err = cn.private['contract'].get_transaction(contract)
    return cn.call_next(nextc, err)

def contract_exec_function(cn, nextc):
    name = cn.rt[cn.rt['contract']]
    err = check.contain(cn.pr, ["kwargs"])
    if not err[0]:
        return cn.toret.add_error(err[1], err[2])
    sender = None
    if 'from_user_wallet' in cmd and cmd['from_user_wallet'] is True:
        sender = cn.private['account'].get_all(anon=False)[1].get('wallets', []).get(0, None)
    err = cn.private['contract'].exec_function(name, cn.pr["kwargs"], sender=sender)
    return cn.call_next(nextc, err)

def contract(cn, nextc):
    id = cn.get.get('id')
    expand = cn.get.get('expand')
    expand = True if expand is not None else False
    err = Contract(' ', cn.private['network_type'], cn.private['network']).get_contract(id, expand)
    return cn.call_next(nextc, err)

def contract_cmd(cn, nextc):
    err = check.contain(cn.pr, ["cmd_list"])
    if not err[0]:
        return cn.toret.add_error(err[1], err[2])
    ret = []
    print(cn.pr)
    for cmd in cn.pr["cmd_list"]:
        sender = None
        if 'from_user_wallet' in cmd and cmd['from_user_wallet'] is True:
            sender = cn.private['account'].get_all(anon=False)[1].get('wallets', []).get(0, None)
        ret.append(cn.private['contract'].exec_function(cmd["name"], cmd["kwargs"], wait=False, sender=sender))
        print(ret)
    err = [True, {'return': ret}, None]
    return cn.call_next(nextc, err)

def email_to_address(cn, nextc):
    err = [True, {}, None]
    for arg in [cn.pr, cn.get]:
        arg = Utils.json_email_replace(
            arg,
            [
                {
                    "func": cn.private["sso"].user_by_email,
                    "res": [1, 'id']
                },
                {
                    "func": Account().get_all,
                    "res": [1, 'wallets', 0, 'address']
                }
            ]

        )
    return cn.call_next(nextc, err)
