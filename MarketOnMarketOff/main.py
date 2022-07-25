# region imports
from AlgorithmImports import *
# endregion

SIGNAL_BUY = 'buy'
SIGNAL_SELL = 'sell'


class MarketOnMarketOff(QCAlgorithm):
    def Initialize(self):
        self.SetStartDate(2021, 1, 24)
        self.SetCash(100000)
        self.AddEquity("SPY", Resolution.Daily)
        self.data = None

    def OnData(self, slice: Slice):
        if not self.data:
            self.data = SymbolData(self.History(self.Symbol('SPY'), 50, Resolution.Daily))
        else:
            self.data.update(self.Time, slice.close, slice.volume)
        if not self.Portfolio.Invested:
            # If there are no recent distribution days and we're not invested, buy.


class SymbolData:
    def __init__(self, history):
        self.dd_window = RollingWindow[int](50)
        self.ftd_window = RollingWindow[int](50)
        self.vol_ma = SimpleMovingAverage(50)
        self.max = Maximum(200)
        self.min = Minimum(200)
        self.previous_vol = None
        self.previous_close = None
        self.signal = None

        for data in history.itertuples():
            self.update(data.Index[1], data.close, data.volume)

    def update(self, time, close, volume):
        self.vol_ma.Update(time, volume)
        self.max.Update(close)
        self.min.Update(close)
        if self.previous_close and self.previous_vol:
            day_change = (close - self.previous_close) / close
            is_distribution_day = day_change < -0.02 and volume > self.previous_vol
            is_follow_through_day = day_change > 0.17 and volume > self.previous_vol and volume > self.vol_ma.Current.Value
            self.dd_window.Add(1 if is_distribution_day else 0)
            self.ftd_window.Add(1 if is_follow_through_day else 0)
        self.previous_close = close
        self.previous_vol = volume

    def market_in_distribution(self):
        return sum(list(self.dd_window)) > 5

    def market_on(self):
        """
        There has been a rally day and a follow through day after a recent bottom.
        The market isn't in distribution
        :return: boolean
        """
        if self.signal == SIGNAL_SELL:
            self.min.PeriodsSinceMinimum
        else:
            return not self.market_in_distribution()

    def market_off(self):
        pass
