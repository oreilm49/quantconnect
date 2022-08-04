# region imports
from AlgorithmImports import *
# endregion

SIGNAL_BUY = 'buy'
SIGNAL_SELL = 'sell'
LONG_LOOKBACK = 200
SHORT_LOOKBACK = 50


class MarketOnMarketOff(QCAlgorithm):
    def Initialize(self):
        self.SetStartDate(2018, 1, 1)
        self.SetCash(100000)
        self.qqq = self.AddEquity("QQQ", Resolution.Daily)
        self.sqqq = self.AddEquity("SQQQ", Resolution.Daily)
        self.data = None

    def OnData(self, slice: Slice):
        if not self.data:
            self.data = SymbolData(self.History(self.qqq.Symbol, LONG_LOOKBACK, Resolution.Daily))
        else:
            prices = slice.get(self.qqq.Symbol)
            if prices:
                self.data.update(self.Time, prices.Close, prices.Volume)
                self.data.low_window.Add(prices.Low)
        if not self.data.ready():
            return
        signal = self.data.get_signal()
        if not self.Portfolio.Invested:
            if signal == SIGNAL_BUY:
                self.SetHoldings("QQQ", 1)
            elif signal == SIGNAL_SELL:
                self.SetHoldings("SQQQ", 1)
        else:
            if signal == SIGNAL_BUY and self.ActiveSecurities[self.sqqq.Symbol].Invested:
                self.Liquidate()
                self.SetHoldings("QQQ", 1)
            if signal == SIGNAL_SELL and self.ActiveSecurities[self.qqq.Symbol].Invested:
                self.Liquidate()
                self.SetHoldings("SQQQ", 1)


class SymbolData:
    def __init__(self, history):
        self.dd_window = RollingWindow[int](SHORT_LOOKBACK)
        self.ftd_window = RollingWindow[int](LONG_LOOKBACK)
        self.rally_day_window = RollingWindow[int](LONG_LOOKBACK)
        self.low_window = RollingWindow[float](LONG_LOOKBACK)
        self.vol_ma = SimpleMovingAverage(SHORT_LOOKBACK)
        self.max = Maximum(LONG_LOOKBACK)
        self.min = Minimum(LONG_LOOKBACK)
        self.previous_vol = None
        self.previous_close = None
        self.signal = None

        for data in history.itertuples():
            self.update(data.Index[1], data.close, data.volume)
            self.low_window.Add(data.low)

    def update(self, time, close, volume):
        self.vol_ma.Update(time, volume)
        self.max.Update(time, close)
        self.min.Update(time, close)
        if self.previous_close and self.previous_vol:
            day_change = (close - self.previous_close) / close
            is_distribution_day = day_change < -0.02 and volume > self.previous_vol
            is_follow_through_day = day_change > 0.17 and volume > self.previous_vol and volume > self.vol_ma.Current.Value
            self.dd_window.Add(1 if is_distribution_day else 0)
            self.ftd_window.Add(1 if is_follow_through_day else 0)
            self.rally_day_window.Add(1 if day_change > 0 else 0)
        self.previous_close = close
        self.previous_vol = volume

    def get_signal(self):
        """
        There has been a rally day and a follow through day after a recent bottom.
        The market isn't in distribution
        :return: boolean
        """
        if self.signal in (SIGNAL_SELL, None):
            # find bottom, rally day, follow through day
            # rally day = loop through each day after min day. Look for up day that starts the rally attempt
            # follow through day = loop through each day after rally day. Check ftd conditions
            rally_day_index = None
            for day_index in reversed(range(self.min.PeriodsSinceMinimum)):
                if self.rally_day_window[day_index] == 1:
                    rally_day_index = day_index
                    break
            if rally_day_index is None:
                self.signal = SIGNAL_SELL
                return self.signal
            for ftd_index in reversed(range(rally_day_index)):
                if self.ftd_window[ftd_index] == 1:
                    # check if ftd failed: if the low of the ftd was taken out.
                    # if so, move on to the next ftd_index
                    # if not, exit loop and update buy signal
                    ftd_low_taken_out = np.min(self.low_window[0:ftd_index - 1]) < self.low_window[ftd_index]
                    if ftd_low_taken_out:
                        continue
                    self.signal = SIGNAL_BUY
                    return self.signal
        if self.signal in (SIGNAL_BUY, None):
            market_in_distribution = sum(list(self.dd_window)) > 5
            if market_in_distribution:
                self.signal = SIGNAL_SELL
        return self.signal

    def ready(self):
        return self.dd_window.IsReady and self.ftd_window.IsReady and self.rally_day_window.IsReady and\
            self.low_window.IsReady and self.vol_ma.IsReady and self.max.IsReady and self.min.IsReady
