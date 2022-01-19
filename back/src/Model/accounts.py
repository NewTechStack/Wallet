from Controller.basic import check
from Object.accounts import Account

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

def account_balance_token(cn, nextc):
    err = check.contain(cn.rt, ["wallet"])
    if not err[0]:
        return cn.toret.add_error(err[1], err[2])
    err = check.contain(cn.rt, ["contract"])
    if not err[0]:
        return cn.toret.add_error(err[1], err[2])
    err = cn.private["account"].token_balance(cn.rt["wallet"], cn.rt["contract"])
    return cn.call_next(nextc, err)
