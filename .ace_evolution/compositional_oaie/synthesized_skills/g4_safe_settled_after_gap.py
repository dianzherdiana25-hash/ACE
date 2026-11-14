def skill_is_framed(tok):
    return (tok.endswith(']') and tok.startswith('['))

def macro_ast_43a65c76(_p0, _p1):
    return (_p1 if skill_is_framed(_p0) else 1)

def skill_bounded_margin(gross, fee):
    return ((gross - fee) if (gross > fee) else 0)

def skill_abs_diff(a, b):
    return (skill_bounded_margin(a, b) + skill_bounded_margin(b, a))

def skill_net_settled_after_gap(gross, a, b):
    return skill_bounded_margin(gross, skill_abs_diff(a, b))

def safe_settled_after_gap(tok, gross, a, b):
    return macro_ast_43a65c76(tok, skill_net_settled_after_gap(gross, a, b))
