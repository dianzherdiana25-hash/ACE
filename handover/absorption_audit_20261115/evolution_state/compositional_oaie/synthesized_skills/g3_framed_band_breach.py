def skill_is_framed(tok):
    return (tok.endswith(']') and tok.startswith('['))

def skill_bounded_margin(gross, fee):
    return ((gross - fee) if (gross > fee) else 0)

def skill_abs_diff(a, b):
    return (skill_bounded_margin(a, b) + skill_bounded_margin(b, a))

def skill_band_breach(a, b, tol):
    return (skill_abs_diff(a, b) > tol)

def framed_band_breach(tok, a, b, tol):
    return (skill_is_framed(tok) and skill_band_breach(a, b, tol))
