def skill_bounded_margin(gross, fee):
    return ((gross - fee) if (gross > fee) else 0)

def positive_delta(val, base):
    return skill_bounded_margin(val, base)
