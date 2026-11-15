def skill_is_framed(tok):
    return (tok.endswith(']') and tok.startswith('['))

def safe_framed_len(tok):
    return (len(tok) if skill_is_framed(tok) else 1)
