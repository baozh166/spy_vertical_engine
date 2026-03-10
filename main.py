import argparse
from engine.vertical_engine import VerticalEngine
from models.em_vix import expected_move
from dotenv import load_dotenv
import os

def main():
    parser = argparse.ArgumentParser(description="SPY Vertical Spread Pricing Engine")
    parser.add_argument("--expiration", "-e", type=str, required=True,
                        help="Option expiration date (e.g. 2026-03-06)")
    parser.add_argument("--rate", "-r", type=float, default=0.04,
                        help="Risk-free interest rate (e.g. 0.04 for 4%)")
    parser.add_argument("--opt_type", "-t", type=str, choices=["call", "put"], default="put",
                        help="Option type: call or put")
    parser.add_argument("--position", "-p", type=str, choices=["long", "short"], default="short",
                        help="Vertical spread position: long or short")
    parser.add_argument("--spread_width", "-w", type=int, default=1,
                        help="Width of the vertical spread in dollars")
    parser.add_argument("--confidence", "-c", type=float, default=0.68,
                        help="Confidence level for expected move (e.g. 0.68 or 0.95)")
    parser.add_argument("--S1", "-1", type=float,
                        help="Future spot price to evaluate vertical value at")
    parser.add_argument("--ladder", "-d", action="store_true",
                        help="Run spot ladder instead of single S1")
    parser.add_argument("--moves_pct", "-m", nargs="+", type=float,
                        help="List of percentage moves for spot ladder (e.g. -0.01 0 0.01)")
    parser.add_argument("--manual_hov", "-s", nargs=3, type=float,
                        help="Manually input [bid ask last] for HigerOptionVale(HOV) leg at SPY spot S0")
    parser.add_argument("--manual_lov", "-l", nargs=3, type=float,
                        help="Manually input [bid ask last] for LowerOptionVale(LOV) leg at SPY spot S0")

    args = parser.parse_args()
    load_dotenv()

    api_key = os.getenv("RAPIDAPI_CNBC_KEY")
    engine = VerticalEngine(
        rapidapi_key_cnbc=api_key,
        expiration=args.expiration,
        rate=args.rate,
        opt_type=args.opt_type,
        spread_width=args.spread_width,
        confidence=args.confidence,
        position=args.position,
        manual_hov=args.manual_hov,
        manual_lov=args.manual_lov,
    )

    engine.clear_cache()

    if args.ladder:
        moves_pct = args.moves_pct if args.moves_pct else [-0.01, -0.005, 0, 0.005, 0.01]
        engine.spot_ladder(moves_pct=moves_pct)

    elif args.S1:
        result = engine.vertical_value_sticky_strike(S1=args.S1)

        # Compute expected move at S0 for reporting
        VIX = result["vix"]
        lower, upper, move = result["expected_move"]
 
        print("\n==== Vertical Spread Value at S₁ ====")
        print(f"Option Type = {engine.opt_type}")
        print(f"Expiration = {engine.expiration}")
        print(f"Confidence Level = {engine.confidence}")
        print(f"Expected Move at VIX = {VIX}: ±${move} → [{lower}, {upper}]")
        print(f"Vertical Spread Position = {engine.position}")
        print("-" * 50)

        # Extract strikes
        K_HOV = result["K_HOV"] # the strike that has higher value
        K_LOV  = result["K_LOV"]  # the strkie that has lower value

        # Position-aware ordering
        if engine.position == "short":
            leg1_name, leg1_val = "HOV_short", K_HOV
            leg2_name, leg2_val = "LOV_long",  K_LOV
        else:
            leg1_name, leg1_val = "HOV_long",  K_HOV
            leg2_name, leg2_val = "LOV_short", K_LOV

        # Print in clean, trader-friendly order
        print(f"Spot S0: {result['S0']}")
        print(f"future spot S1: {result['S1']}")
        print(f"K_{leg1_name}: {leg1_val}")
        print(f"K_{leg2_name}: {leg2_val}")
        print(f"P_{leg1_name}_mkt:  {result['p_HOV_mkt']}")
        print(f"P_{leg2_name}_mkt:  {result['p_LOV_mkt']}")
        print(f"Vertical mkt at S0: {result['vertical_mkt_at_s0']}")
        print(f"P_{leg1_name}_BSM at S1:  {result['p_HOV_bsm']}")
        print(f"P_{leg2_name}_BSM at S1:  {result['p_LOV_bsm']}")
        print(f"Vertical BSM at S1: {result['vertical_bsm_at_s1']}")
        print("-" * 50)

    else:
        print("Please provide either --S1 or --ladder to run the engine.")

if __name__ == "__main__":
    main()

