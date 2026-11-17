def skill_is_framed(tok):
    return (tok.endswith(']') and tok.startswith('['))

def skill_bounded_margin(gross, fee):
    return ((gross - fee) if (gross > fee) else 0)

def framed_margin(tok, gross, fee):
    return (skill_bounded_margin(gross, fee) if skill_is_framed(tok) else 1)
