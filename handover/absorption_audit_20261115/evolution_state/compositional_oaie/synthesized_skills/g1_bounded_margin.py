def bounded_margin(gross, fee):
    return ((gross - fee) if (gross > fee) else 0)
