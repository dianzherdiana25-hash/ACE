def is_framed(tok):
    return (tok.endswith(']') and tok.startswith('['))
