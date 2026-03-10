import yfinance as yf

def get_option_mkt_price(expiration, strike, opt_type, manual_input=None):
    # --- Manual override mode ---
    if manual_input is not None:
        bid, ask, last = manual_input
        return {"bid": bid, 
                "ask": ask, 
                "last_price": last}
    
    # --- Default: use yfinance ---
    spy = yf.Ticker("SPY")
    chain = spy.option_chain(expiration)
    df = chain.calls if opt_type == "call" else chain.puts

    row = df[df["strike"] == strike]
    if row.empty:
        raise ValueError(f"No option found at strike {strike}")

    return {
        "bid": float(row["bid"].iloc[0]),
        "ask": float(row["ask"].iloc[0]),
        "last_price": float(row["lastPrice"].iloc[0]),
    }