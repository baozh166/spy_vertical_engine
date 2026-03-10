import math
from scipy.stats import norm

def expected_move(spot, vix, days, confidence=0.68):
    vol_annual = vix / 100.0
    vol_period = vol_annual * math.sqrt(days / 252)

    if confidence == 0.68:
        sigma = 1
    elif confidence == 0.95:
        sigma = 2
    else:
        sigma = norm.ppf((1 + confidence) / 2)

    move = round(spot * vol_period * sigma, 2)
    lower = round(spot - move, 2)
    upper = round(spot + move, 2)
    return lower, upper, move
