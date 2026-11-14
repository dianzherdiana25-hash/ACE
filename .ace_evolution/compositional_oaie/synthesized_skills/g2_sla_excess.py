def skill_bounded_margin(gross, fee):
    return ((gross - fee) if (gross > fee) else 0)

def skill_abs_diff(a, b):
    return (skill_bounded_margin(a, b) + skill_bounded_margin(b, a))

def sla_excess(a, b, tol):
    return skill_bounded_margin(skill_abs_diff(a, b), tol)
