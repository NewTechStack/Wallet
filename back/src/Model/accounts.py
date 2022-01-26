from Controller.basic import check
from Object.accounts import Account
from Object.contracts import *

def account_load(cn, nextc):
    usr_id = None
    if 'sso' in cn.private:
        usr_id = cn.private["sso"].user["id"]
    cn.private["account"] = Account(usr_id)
    err = [True, {}, None]
    return cn.call_next(nextc, err)

def blockcahin_status(cn, nextc):
    err = cn.private["account"].status()
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

def contract_type(cn, nextc):
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

def contract_get_function(cn, nextc):
    err = cn.private['contract'].get_functions()
    return cn.call_next(nextc, err)

def contract_exec_constructor(cn, nextc):
    err = check.contain(cn.pr, ["kwargs"])
    if not err[0]:
        return cn.toret.add_error(err[1], err[2])
    err = cn.private['contract'].deploy(cn.pr["kwargs"])
    return cn.call_next(nextc, err)

def contract_get_constructor(cn, nextc):
    err = cn.private['contract'].get_constructor()
    return cn.call_next(nextc, err)

def contract_exec_function(cn, nextc):
    name = cn.rt[cn.rt[cn.rt['contract']]]
    err = check.contain(cn.pr, ["kwargs"])
    if not err[0]:
        return cn.toret.add_error(err[1], err[2])
    err = cn.private['contract'].exec_function(name, cn.pr["kwargs"])
    return cn.call_next(nextc, err)

def contract(cn, nextc):
    id = cn.get.get('id')
    expand = cn.get.get('expand')
    expand = True if expand is not None else False
    err = Contract('').get_contract(id, expand)
    return cn.call_next(nextc, err)
