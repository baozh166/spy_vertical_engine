import math
from dataclasses import dataclass
from scipy.stats import norm
from typing import Literal

OptionType = Literal["call", "put"]

@dataclass
class OptionContract:
    spot: float
    strike: float
    rate: float
    days_to_expiry: int
    iv: float
    opt_type: OptionType

    @property
    def T(self):
        return self.days_to_expiry / 252.0

    def d1_d2(self):
        S, K, r, T, sigma = self.spot, self.strike, self.rate, self.T, self.iv
        if sigma <= 0 or T <= 0:
            raise ValueError("sigma and T must be positive")
        d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)
        return d1, d2

    def price(self):
        S, K, r, T, sigma = self.spot, self.strike, self.rate, self.T, self.iv
        d1, d2 = self.d1_d2()
        if self.opt_type == "call":
            return S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
        else:
            return K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
