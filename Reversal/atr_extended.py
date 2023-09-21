def calculate_atr_extended_multiples(atr, ma, close_price) -> int:
    """
    Measures stock price extension from the 50 day.
    Useful for determining if it's an appropriate time to take profits.
    Stocks can stall and decline after exceeding 7 - 10 times the ATR% from its 50-day moving average.
    """
    atr_percent = atr.Current.Value / close_price
    gain_from_ma = (close_price - ma.Current.Value) / ma.Current.Value * 100
    return gain_from_ma / atr_percent