# region imports
from AlgorithmImports import *
# endregion

class CryptoMomentum(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2018, 1, 1)
        self.SetCash(100000)
        self.symbol = self.AddCrypto('BTCUSD', Resolution.Daily).Symbol

        self.ema = self.EMA(self.symbol, 21, Resolution.Daily)
        self.ma = self.SMA(self.symbol, 50, Resolution.Daily)
        self.ema_window = RollingWindow[int](3)

    def OnData(self, data: Slice):
        if not data.Bars.ContainsKey(self.symbol):
            return
        close = data.Bars[self.symbol].Close
        ema = self.ema.Current.Value
        self.ema_window.Add(ema)
        ema_vals = list(reversed(list(self.ema_window)))
        ema_increasing = all(prev_val < next_val for prev_val, next_val in zip(ema_vals, ema_vals[1:]))
        if not self.Portfolio.Invested:
            if close > ema:
                if ema_increasing:
                    if ema > self.ma.Current.Value:
                        self.MarketOrder(self.symbol, 1)
        elif close < ema or not ema_increasing or ema < self.ma.Current.Value:
            self.Liquidate()
