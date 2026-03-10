from scipy.optimize import brentq
from .bsm import OptionContract, OptionType

def implied_vol(
    market_price: float,
    spot: float,
    strike: float,
    rate: float,
    days_to_expiry: int,
    opt_type: OptionType,
    iv_lower=0.0001, iv_upper=5.0, tol=1e-6
) -> float:
    
    """
    Solve for implied volatility using Brent's method.
    The core idea is to find the volatility value that makes the theoretical option price from a model (e.g., Black-Scholes)
    equal to the observed market price.
    This is done by defining an objective function and finding its root using a numerical optimization algorithm.
    """

    def objective(iv):
        opt = OptionContract(
            spot=spot,
            strike=strike,
            rate=rate,
            days_to_expiry=days_to_expiry,
            iv=iv,
            opt_type=opt_type,
        )
        return opt.price() - market_price

    return brentq(objective, iv_lower, iv_upper, xtol=tol)
