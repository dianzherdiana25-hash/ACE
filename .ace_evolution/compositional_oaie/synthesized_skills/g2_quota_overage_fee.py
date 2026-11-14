def skill_bounded_margin(gross, fee):
    return ((gross - fee) if (gross > fee) else 0)

def quota_overage_fee(used, cap, rate):
    return (skill_bounded_margin(used, cap) * rate)
