from AlgorithmImports import RollingWindow, TradeBar, Resolution
from datetime import timedelta

from reversal_day import ReversalDayIndicator


class SymbolIndicators:
    def __init__(self, algorithm, symbol) -> None:
        self.algorithm = algorithm
        self.trade_bar_window = RollingWindow[TradeBar](50)

        history = algorithm.History(symbol, 200, Resolution.Daily)
        for data in history.itertuples():
            trade_bar = TradeBar(data.Index[1], data.Index[0], data.open, data.high, data.low, data.close, data.volume, timedelta(1))
            self.update(trade_bar)
    
    def update(self, trade_bar):
        self.trade_bar_window.Add(trade_bar)
    
    @property
    def reversal(self) -> ReversalDayIndicator:
        return ReversalDayIndicator(self.trade_bar_window)