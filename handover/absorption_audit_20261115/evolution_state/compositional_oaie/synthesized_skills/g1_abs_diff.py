def skill_bounded_margin(gross, fee):
    return ((gross - fee) if (gross > fee) else 0)

def abs_diff(a, b):
    return (skill_bounded_margin(a, b) + skill_bounded_margin(b, a))
