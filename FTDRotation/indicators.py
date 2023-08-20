from typing import Optional

from AlgorithmImports import RollingWindow, TradeBar, RateOfChangePercent, SimpleMovingAverage, AverageTrueRange
import constants


class MarketIndexData:
    def __init__(self, history):
        self.dd_window = RollingWindow[int](10)
        self.ftd: Optional[TradeBar] = None
        self.vol_ma = SimpleMovingAverage(50)
        self.previous_vol = None
        self.previous_close = None

        for trade_bar in history.itertuples():
            self.update(trade_bar)

    def update(self, trade_bar):
        time, close, volume = trade_bar.EndTime, trade_bar.Close, trade_bar.Volume
        self.vol_ma.Update(time, volume)
        if self.previous_close and self.previous_vol:
            day_change = (close - self.previous_close) / close
            self.dd_window.Add(1 if day_change < -0.02 and volume > self.previous_vol else 0)
            # Follow through day logic
            if day_change > 0.17 and volume > self.previous_vol and volume > self.vol_ma.Current.Value:
                self.ftd = trade_bar
            if self.ftd and (time - self.ftd.Index).days > 5:
                if self.distribution or (self.previous_close < self.ftd.Close):
                    self.ftd = None
        self.previous_close = close
        self.previous_vol = volume
    
    @property
    def distribution(self) -> bool:
        return sum(self.dd_window) >= 6
    
    def status(self) -> str:
        if self.distribution:
            return constants.SIGNAL_SELL
        elif self.ftd:
            return constants.SIGNAL_BUY

    def ready(self) -> bool:
        return self.dd_window.IsReady and self.vol_ma.IsReady
    

class SymbolIndicators:
    def __init__(self, history) -> None:
        self.roc = RateOfChangePercent(50)
        self.atr = AverageTrueRange(21)

        for trade_bar in history.itertuples():
            self.update(trade_bar)
        
    def update(self, trade_bar):
        self.roc.Update(trade_bar.EndTime, trade_bar.Close)
        self.atr.Update(trade_bar)
    
    @property
    def ready(self):
        return all((
            self.roc.IsReady,
            self.atr.IsReady,
        ))