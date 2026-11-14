def skill_bounded_margin(gross, fee):
    return ((gross - fee) if (gross > fee) else 0)

def skill_abs_diff(a, b):
    return (skill_bounded_margin(a, b) + skill_bounded_margin(b, a))

def net_settled_after_gap(gross, a, b):
    return skill_bounded_margin(gross, skill_abs_diff(a, b))
