from AlgorithmImports import RollingWindow, TradeBar, Resolution, AverageTrueRange, SimpleMovingAverage
from datetime import timedelta

from atr_extended import calculate_atr_extended_multiples
from reversal_day import ReversalDayIndicator


class SymbolIndicators:
    def __init__(self, algorithm, symbol) -> None:
        self.algorithm = algorithm
        self.trade_bar_window = RollingWindow[TradeBar](2)
        self.atr = AverageTrueRange(21)
        self.ma = SimpleMovingAverage(50)
        self.vol_ma = SimpleMovingAverage(50)

        history = algorithm.History(symbol, 50, Resolution.Daily)
        for data in history.itertuples():
            trade_bar = TradeBar(data.Index[1], data.Index[0], data.open, data.high, data.low, data.close, data.volume, timedelta(1))
            self.update(trade_bar)
    
    def update(self, trade_bar):
        self.trade_bar_window.Add(trade_bar)
        self.atr.Update(trade_bar)
        self.ma.Update(trade_bar.EndTime, trade_bar.Close)
        self.vol_ma.Update(trade_bar.EndTime, trade_bar.Volume)
    
    @property
    def reversal(self) -> ReversalDayIndicator:
        return ReversalDayIndicator(self.trade_bar_window)
    
    @property
    def extended_from_ma(self) -> bool:
        return calculate_atr_extended_multiples(self.atr, self.ma, self.trade_bar_window[0].Close) >= 7
    
    @property
    def huge_volume(self) -> bool:
        return self.trade_bar_window[0].Volume > self.vol_ma.Current.Value * 1.5
    
    @property
    def ready(self):
        return all((
            self.atr.IsReady,
            self.vol_ma.IsReady,
            self.ma.IsReady,
            self.trade_bar_window.IsReady,
        ))