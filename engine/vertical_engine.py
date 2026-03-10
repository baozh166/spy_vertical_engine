from models.iv_solver import implied_vol
from models.bsm import OptionContract
from models.em_vix import expected_move
from utils.data import get_spy_spot_price, get_vix_cnbc
from utils.count_days import count_trading_days
from utils.option_chain import get_option_mkt_price
from .price_selection import choose_price_buy, choose_price_sell
import math
import numpy as np
from typing import Literal, List

class VerticalEngine:
    def __init__(self, rapidapi_key_cnbc, expiration, rate=0.04,
                 opt_type="put", spread_width=1, confidence=0.68,
                 position="short", manual_hov=None, manual_lov=None):

        self.rapidapi_key_cnbc = rapidapi_key_cnbc
        self.expiration = expiration
        self.rate = rate
        self.opt_type = opt_type
        self.spread_width = spread_width
        self.confidence = confidence
        self.position = position
        self.manual_hov = manual_hov
        self.manual_lov = manual_lov
        self._iv_cache = None

    # ---------- automaticly select strikes ----------
    def get_HOV_LOV_strikes(self, spot_price: float, vix: float, days: int): 
        lower, upper, move = expected_move(spot_price, vix, days, confidence=self.confidence)

        if self.opt_type == "put":
            K_HOV = int(lower)                 # K_HOV = strike for higher option value, K_LOV = strike for lower option value
            K_LOV = K_HOV - self.spread_width  # For puts, higher strike has higher option value, so K_LOV is below K_HOV
        else:
            K_HOV = math.ceil(upper)
            K_LOV = K_HOV + self.spread_width

        return K_HOV, K_LOV, (lower, upper, move)
    
    # ----------------- IV at S0 -----------------
    def compute_iv_at_s0(self):
        # Return cached result if available
        if self._iv_cache is not None:
            return self._iv_cache

        spot = get_spy_spot_price()
        vix = get_vix_cnbc(api_key = self.rapidapi_key_cnbc)
        days = count_trading_days(expiration = self.expiration)

        # Determine higher-value and lower-value strikes
        # (lower, upper, move) are returned for reporting but not used in IV calculation    
        K_HOV, K_LOV, (lower, upper, move) = self.get_HOV_LOV_strikes(spot, vix, days)
        
        # Market quotes for the vertical's two legs
        opt_HOV = get_option_mkt_price(self.expiration, K_HOV, self.opt_type, manual_input=self.manual_hov)
        opt_LOV = get_option_mkt_price(self.expiration, K_LOV, self.opt_type, manual_input=self.manual_lov)

        bid_HOV = max(opt_HOV["bid"], 0)
        ask_HOV = max(opt_HOV["ask"], 0)
        last_HOV = opt_HOV["last_price"]

        bid_LOV = max(opt_LOV["bid"], 0)
        ask_LOV = max(opt_LOV["ask"], 0)
        last_LOV = opt_LOV["last_price"]

        # -----------------------------
        # Position-aware price selection
        # -----------------------------
        if self.position == "short": 
            # Short vertical spread:
            #   Sell HOV at bid (fallback: synthetic bid)
            #   Buy  LOV at ask (fallback: synthetic ask)
            HOV_mkt_price = bid_HOV if bid_HOV != 0 else choose_price_sell(ask_HOV, last_HOV)
            LOV_mkt_price = ask_LOV if ask_LOV != 0 else choose_price_buy(bid_LOV, last_LOV)

        else:
            # Long vertical spread:
            #   Buy  HOV at ask (fallback: synthetic ask)
            #   Sell LOV at bid (fallback: synthetic bid)
            HOV_mkt_price = ask_HOV if ask_HOV != 0 else choose_price_buy(bid_HOV, last_HOV)
            LOV_mkt_price = bid_LOV if bid_LOV != 0 else choose_price_sell(ask_LOV, last_LOV)

        # -----------------------------
        # Compute IVs using chosen prices
        # -----------------------------
        iv_HOV = implied_vol(
            market_price=HOV_mkt_price,
            spot=spot,
            strike=K_HOV,
            rate=self.rate,
            days_to_expiry=days,
            opt_type=self.opt_type,
        )

        iv_LOV = implied_vol(
            market_price=LOV_mkt_price,
            spot=spot,
            strike=K_LOV,
            rate=self.rate,
            days_to_expiry=days,
            opt_type=self.opt_type,
        )

        info = {
            "spot": spot,
            "vix": vix,
            "days": days,
            "K_HOV": K_HOV,
            "K_LOV": K_LOV,
            "iv_HOV": iv_HOV,
            "iv_LOV": iv_LOV,
            "HOV_mkt_price": HOV_mkt_price,
            "LOV_mkt_price": LOV_mkt_price,
            "expected_move": (lower, upper, move)
        }
        self._iv_cache = info  # cache the result
        return info
    
    # ---------- cache management ----------
    def clear_cache(self):
        self._iv_cache = None

    # Fields that require cache invalidation when changed
    _CACHE_SENSITIVE_FIELDS = {
        "position",
        "manual_hov",
        "manual_lov",
        "expiration",
        "opt_type",
    }

    def __setattr__(self, name, value):
        # If this attribute affects IV-at-S0, clear cache
        if hasattr(self, "_iv_cache") and name in self._CACHE_SENSITIVE_FIELDS:
            super().__setattr__("_iv_cache", None)

        # Perform normal assignment
        super().__setattr__(name, value)


    # ---------- pricing at S1 ----------
    def price_leg_at_future_spot(
        self, S1: float, strike: float, days: int, iv: float
    ) -> float:
        opt_bsm = OptionContract(
            spot=S1,
            strike=strike,
            rate=self.rate,
            days_to_expiry=days,
            iv=iv,
            opt_type=self.opt_type,
        )
        return round(opt_bsm.price(), 2)

    def vertical_value_sticky_strike(self, S1: float) -> dict:
        info = self.compute_iv_at_s0()
        K_HOV = info["K_HOV"]
        K_LOV = info["K_LOV"]
        days = info["days"]
        iv_HOV = info["iv_HOV"]
        iv_LOV = info["iv_LOV"]
        spot = info["spot"]
        vix = info["vix"]
        HOV_mkt_price = info["HOV_mkt_price"]
        LOV_mkt_price = info["LOV_mkt_price"]
        expected_move = info["expected_move"]

        sign = -1 if self.position == "short" else 1
        
        # Price each leg at future spot S1 using the IVs derived from spot S0 
        p_HOV_bsm = self.price_leg_at_future_spot(S1, K_HOV, days, iv_HOV)
        p_LOV_bsm = self.price_leg_at_future_spot(S1, K_LOV, days, iv_LOV)

        # The vertical spread value at S1 is the difference in leg values, with sign depending on position
        vertical_bsm_at_s1 = round(sign * (p_HOV_bsm - p_LOV_bsm), 2)

        # For comparison, provide the vertical's market value at S0
        vertical_mkt_at_s0 = round(sign * (HOV_mkt_price - LOV_mkt_price), 2)

        return {
            "S0": spot,
            "S1": S1,
            "vix": vix,
            "days": days,
            "K_HOV": K_HOV,
            "K_LOV": K_LOV,
            "p_HOV_mkt": HOV_mkt_price,
            "p_LOV_mkt": LOV_mkt_price,
            "vertical_mkt_at_s0": vertical_mkt_at_s0,
            "p_HOV_bsm": p_HOV_bsm,
            "p_LOV_bsm": p_LOV_bsm,
            "vertical_bsm_at_s1": vertical_bsm_at_s1,
            "expected_move": expected_move
        }

    # ------------- spot ladder -------------
    def spot_ladder(self, moves_pct: List[float]):
        S0 = get_spy_spot_price()

        # Determine column labels based on position
        if self.position == "short":
            col1, col2 = "K_HOV_short", "K_LOV_long"
        else: 
            # long vertical
            col1, col2 = "K_HOV_long", "K_LOV_short"

        print("\n==== SPOT LADDER (Sticky Strike) ====")
        print(f"Option Type = {self.opt_type}")
        print(f"Expiration = {self.expiration}")
        print(f"Confidence Level = {self.confidence}")
        print(f"Vertical Spread Position = {self.position}")
        print(f"SPY spot S0 = {S0}")
        print("-" * 82)
        print(f"{'S1':>8} | {col1:>12} | {col2:>12} | {'Vertical mkt at S0':>18} | {'Vertical bsm at S1':>18}")
        print("-" * 82)
        
        vixs = []
        expected_moves = []
        for pct in moves_pct:
            S1 = round(S0 * (1 + pct), 2)
            res = self.vertical_value_sticky_strike(S1)

            # Extract strikes
            K_HOV = res["K_HOV"]
            K_LOV = res["K_LOV"]
            # Extract vertical spread values
            val_0 = res["vertical_mkt_at_s0"]
            val_1 = res["vertical_bsm_at_s1"]

            # vix and expected move for reporting
            vixs.append(res["vix"])
            expected_moves.append(res["expected_move"])

            print(f"{S1:>8} | {K_HOV:>12} | {K_LOV:>12} | {val_0:>18.2f} | {val_1:>18.2f}")
        print("-" * 82)

        # report expected move at S0 (should be the same across ladder since it's based on S0's IV and VIX)
        VIX = set(vixs).pop()  # all vix values should be the same, so we can just take one
        lower, upper, move = set(expected_moves).pop()  # all expected move values should be the same
        print(f"Expected Move at VIX = {VIX}: ±${move} → [{lower}, {upper}]")