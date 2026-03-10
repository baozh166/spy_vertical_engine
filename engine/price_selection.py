def choose_price_sell(ask, last):
    """
    Price selection when SELLING an option and bid = 0.
    """
    # If ask is missing or zero, last is the only usable reference
    if ask == 0:
        return last

    # If last is significantly above ask → stale or crossed
    # Use a optimistic synthetic bid (0.6 * ask)
    if last > 1.2 * ask:
        return 0.6 * ask

    return last

def choose_price_buy(bid, last):
    """
    Price selection when BUYING an option and ask = 0.
    """
    # Safety clamp: bid cannot be negative
    bid = max(bid, 0)

    # If bid is missing or zero, last is the only usable reference
    if bid == 0:
        return last

    # If last is below bid, it's stale → use synthetic ask
    if last < bid:
        return 1.2 * bid   # synthetic ask

    return last
