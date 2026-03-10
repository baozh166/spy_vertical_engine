import yfinance as yf
import requests

def get_spy_spot_price():
    spy = yf.Ticker("SPY")
    data = spy.history(period="1d", interval="1m", prepost=True)
    spot = round(float(data["Close"].iloc[-1]), 2)
    return spot

def get_vix_cnbc(api_key):
    url = "https://cnbc.p.rapidapi.com/market/list-indices"
    headers = {"x-rapidapi-host": "cnbc.p.rapidapi.com", 
               "x-rapidapi-key": api_key}
    
    data = requests.get(url, headers=headers).json()
    for item in data["ITVQuoteResult"]["ITVQuote"]:
        if item["symbol"] == ".VIX":
            return float(item["last"]) # using "last" price as spot for VIX
        
    raise RuntimeError("VIX not found")
