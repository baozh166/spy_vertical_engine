import yfinance as yf
import math
from dataclasses import dataclass
from typing import Literal, List
from scipy.stats import norm
from scipy.optimize import brentq
import pandas_market_calendars as mcal
import pandas as pd
import requests
from dotenv import load_dotenv
import os


# ---------------------------- # "call" or "put" only # ----------------------------
OptionType = Literal["call", "put"]


# ---------------------------- # pricing option via BSM # ----------------------------
@dataclass
class OptionContract:
    spot: float
    strike: float
    rate: float
    days_to_expiry: int
    iv: float
    opt_type: OptionType

    @property
    def T(self) -> float:
        return self.days_to_expiry / 252.0

    def d1_d2(self):
        S, K, r, T, sigma = self.spot, self.strike, self.rate, self.T, self.iv
        if sigma <= 0 or T <= 0:
            raise ValueError("sigma and T must be positive")
        d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)
        return d1, d2

    def price(self) -> float:
        S, K, r, T, sigma = self.spot, self.strike, self.rate, self.T, self.iv
        d1, d2 = self.d1_d2()
        if self.opt_type == "call":
            return S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
        else:
            return K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)


# ---------------------------- # calculate IV from market value # ----------------------------
def implied_vol(
    market_price: float,
    spot: float,
    strike: float,
    rate: float,
    days_to_expiry: int,
    opt_type: OptionType,
    iv_lower: float = 0.0001,
    iv_upper: float = 5.0,
    tol: float = 1e-6,
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


# --------------------------------- # vertical engine core # ---------------------------------
class VerticalEngine:
    def __init__(
        self,
        rapidapi_key_cnbc: str,
        expiration: str,
        rate: float = 0.04,
        opt_type: OptionType = "call",
        spread_width: int = 1,
        confidence: float = 0.68,
        position: Literal["long", "short"] = "short"

    ):
        self.rapidapi_key_cnbc = rapidapi_key_cnbc
        self.expiration = expiration
        self.rate = rate
        self.opt_type = opt_type
        self.spread_width = spread_width
        self.confidence = confidence
        self.position = position


    # ---------- data helpers ----------

    def get_spy_spot_price(self) -> float:
        spy = yf.Ticker("SPY")
        data = spy.history(period="1d", interval="1m", prepost=True)
        spot = round(float(data["Close"].iloc[-1]), 2)
        return spot

    def get_vix_cnbc(self) -> float:
        url = "https://cnbc.p.rapidapi.com/market/list-indices"
        headers = {
            "x-rapidapi-host": "cnbc.p.rapidapi.com",
            "x-rapidapi-key": self.rapidapi_key_cnbc,
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        symbol_lst = data["ITVQuoteResult"]["ITVQuote"]

        vix_last = None
        for item in symbol_lst:
            if item["symbol"] == ".VIX":
                vix_last = float(item["last"])
                break

        if vix_last is None:
            raise RuntimeError("VIX (.VIX) not found in CNBC response")

        return vix_last

    def get_option_mkt_price(self, strike: float):
        spy = yf.Ticker("SPY")
        chain = spy.option_chain(self.expiration)
        df = chain.calls if self.opt_type == "call" else chain.puts
        row = df[df["strike"] == strike]
        if row.empty:
            raise ValueError(f"No option found at strike {strike}")
        return {
            "last_price": float(row["lastPrice"].iloc[0]),
            "bid": float(row["bid"].iloc[0]),
            "ask": float(row["ask"].iloc[0]),
            "implied_vol": float(row["impliedVolatility"].iloc[0]),
            "volume": int(row["volume"].iloc[0]),
            "open_interest": int(row["openInterest"].iloc[0]),
        }

    def count_trading_days(self) -> int:
        nyse = mcal.get_calendar("NYSE")
        schedule = nyse.schedule(
            start_date=pd.Timestamp.now(), end_date=self.expiration
        )
        return len(schedule)

    # ---------- expected move & strikes ----------

    def expected_move(self, spot_price: float, vix: float, days: int):
        vol_annual = vix / 100.0
        vol_period = vol_annual * math.sqrt(days / 252)

        if self.confidence == 0.68:
            sigma = 1
        elif self.confidence == 0.95:
            sigma = 2
        else:
            sigma = norm.ppf((1 + self.confidence) / 2)

        move = round(spot_price * vol_period * sigma, 2)
        lower = round(spot_price - move, 2)
        upper = round(spot_price + move, 2)
        return lower, upper, move

    def get_short_long_strikes(self, spot_price: float, vix: float, days: int):
        lower, upper, _ = self.expected_move(spot_price, vix, days)

        if self.opt_type == "put":
            K_short = int(lower)
            K_long = K_short - self.spread_width
        else:
            K_short = math.ceil(upper)
            K_long = K_short + self.spread_width

        return K_short, K_long

    # ---------- IV at S0 ----------

    def compute_iv_at_s0(self):
        spot = self.get_spy_spot_price()
        vix = self.get_vix_cnbc()
        days = self.count_trading_days()

        K_short, K_long = self.get_short_long_strikes(spot, vix, days)

        opt_short = self.get_option_mkt_price(K_short)
        opt_long = self.get_option_mkt_price(K_long)

        bid_short = opt_short["bid"]
        ask_short = opt_short["ask"]
        last_short = opt_short["last_price"]

        bid_long = opt_long["bid"]
        ask_long = opt_long["ask"]
        last_long = opt_long["last_price"]

        short_mkt_price = bid_short if bid_short != 0 else last_short
        long_mkt_price = ask_long if ask_long != 0 else last_long

        iv_short = implied_vol(
            market_price=short_mkt_price,
            spot=spot,
            strike=K_short,
            rate=self.rate,
            days_to_expiry=days,
            opt_type=self.opt_type,
        )

        iv_long = implied_vol(
            market_price=long_mkt_price,
            spot=spot,
            strike=K_long,
            rate=self.rate,
            days_to_expiry=days,
            opt_type=self.opt_type,
        )

        return {
            "spot": spot,
            "vix": vix,
            "days": days,
            "K_short": K_short,
            "K_long": K_long,
            "iv_short": iv_short,
            "iv_long": iv_long,
            "opt_short": opt_short,
            "opt_long": opt_long,
        }

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
        spot = info["spot"]
        days = info["days"]
        K_short = info["K_short"]
        K_long = info["K_long"]
        iv_short = info["iv_short"]
        iv_long = info["iv_long"]
        opt_short = info["opt_short"]
        opt_long = info["opt_long"]

        sign = -1 if self.position == "short" else 1

        p_short_mkt = round(opt_short["last_price"], 2)
        p_long_mkt = round(opt_long["last_price"], 2)
        vertical_mkt_at_s0 = round(sign * (p_short_mkt - p_long_mkt), 2)

        p_short_bsm = self.price_leg_at_future_spot(S1, K_short, days, iv_short)
        p_long_bsm = self.price_leg_at_future_spot(S1, K_long, days, iv_long)
        vertical_value_at_s1 = round(sign * (p_short_bsm - p_long_bsm), 2)

        return {
            "S0": spot,
            "S1": S1,
            "K_short": K_short,
            "K_long": K_long,
            "vertical_mkt_at_s0": vertical_mkt_at_s0,
            "vertical_model_at_s1": vertical_value_at_s1,
            "p_short_mkt": p_short_mkt,
            "p_long_mkt": p_long_mkt,
            "p_short_bsm": p_short_bsm,
            "p_long_bsm": p_long_bsm,
        }

    # ---------- spot ladder ----------

    def spot_ladder(self, pct_moves: List[float]):
        S0 = self.get_spy_spot_price()
        print("\n==== SPOT LADDER (Sticky Strike) ====")
        print(f"Underlying S0 = {S0}")
        print(f"Option type = {self.opt_type}")
        print(f"Expiration = {self.expiration}")
        print(f"Confidence = {self.confidence}")
        print(f"vertical spread position = {self.position}")
        print("-" * 80)
        print(f"{'S1':>8} | {'K_short':>8} | {'K_long':>8} | {'Vertical mkt at S0':>20} | {'Vertical Value at S1':>22}")
        print("-" * 80)

        for pct in pct_moves:
            S1 = round(S0 * (1 + pct), 2)
            res = self.vertical_value_sticky_strike(S1)

            val_1 = res["vertical_model_at_s1"]
            val_0 = res["vertical_mkt_at_s0"]
            K_short = res["K_short"]
            K_long = res["K_long"]

            print(f"{S1:>8} | {K_short:>8} | {K_long:>8} | {val_0:>20.2f} | {val_1:>22.2f}")

        print("-" * 80)


# --------------------------------- # CLI ENTRY POINT # ---------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="SPY Vertical Spread Pricing Engine (Sticky Strike Model)"
    )

    parser.add_argument("--expiration", type=str, required=True,
                        help="Option expiration date (e.g. 2026-03-06)")
    parser.add_argument("--opt_type", type=str, choices=["call", "put"], default="call",
                        help="Option type: call or put")
    parser.add_argument("--position", type=str, choices=["long", "short"], default="short",
                        help="Vertical spread position: long or short")
    parser.add_argument("--spread_width", type=int, default=1,
                        help="Width of the vertical spread in dollars")
    parser.add_argument("--confidence", type=float, default=0.68,
                        help="Confidence level for expected move (e.g. 0.68 or 0.95)")
    parser.add_argument("--S1", type=float,
                        help="Future spot price to evaluate vertical value at")
    parser.add_argument("--ladder", action="store_true",
                        help="Run spot ladder instead of single S1")
    parser.add_argument("--pct_moves", nargs="+", type=float,
                        help="List of percentage moves for spot ladder (e.g. -0.01 0 0.01)")

    args = parser.parse_args()

    load_dotenv()
    # Create a file named .env file, in which write down your rapidapi_key as RAPIDAPI_CNBC_KEY=your_key_here
    rapidapi_key = os.getenv("RAPIDAPI_CNBC_KEY")
    if rapidapi_key is None:
        raise RuntimeError("""Missing RAPIDAPI_CNBC_KEY environment variable: Create a file named .env file, 
                              in which write down your rapidapi_key as RAPIDAPI_CNBC_KEY=your_key_here""")


    # Instantiate engine
    engine = VerticalEngine(
        rapidapi_key_cnbc=rapidapi_key,
        expiration=args.expiration,
        rate=0.04,
        opt_type=args.opt_type,
        spread_width=args.spread_width,
        confidence=args.confidence,
    )

    engine.position = args.position

    if args.ladder:
        pct_moves = args.pct_moves if args.pct_moves else [-0.01, -0.005, 0, 0.005, 0.01]
        engine.spot_ladder(pct_moves=pct_moves)
    elif args.S1:
        result = engine.vertical_value_sticky_strike(S1=args.S1)
        print("\n==== Vertical Spread Value at S₁ ====")
        print(f"Option type = {engine.opt_type}")
        print(f"Expiration = {engine.expiration}")
        print(f"Vertical spread position = {engine.position}")
        print("-" * 50)
        for k, v in result.items():
            print(f"{k}: {v}")
    else:
        print("Please provide either --S1 or --ladder to run the engine.")

