def skill_is_framed(tok):
    return (tok.endswith(']') and tok.startswith('['))

def macro_ast_43a65c76(_p0, _p1):
    return (_p1 if skill_is_framed(_p0) else 1)

def skill_bounded_margin(gross, fee):
    return ((gross - fee) if (gross > fee) else 0)

def skill_quota_overage_fee(used, cap, rate):
    return (skill_bounded_margin(used, cap) * rate)

def framed_overage_charge(tok, used, cap, rate):
    return macro_ast_43a65c76(tok, skill_quota_overage_fee(used, cap, rate))
