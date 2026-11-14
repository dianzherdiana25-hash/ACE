def skill_is_framed(tok):
    return (tok.endswith(']') and tok.startswith('['))

def framed_square(tok, x):
    return ((x * x) if skill_is_framed(tok) else 1)
