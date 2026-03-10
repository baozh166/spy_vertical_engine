import pandas_market_calendars as mcal
import pandas as pd

def count_trading_days(expiration):
    nyse = mcal.get_calendar("NYSE")
    schedule = nyse.schedule(start_date=pd.Timestamp.now(), end_date=expiration)
    return len(schedule)
