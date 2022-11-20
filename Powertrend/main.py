# region imports
from AlgorithmImports import *
# endregion

class SymbolIndicators:
    def __init__(self) -> None:
        self.ma = SimpleMovingAverage(50)
        self.ema = ExponentialMovingAverage(21)
        self.atr = AverageTrueRange(21)
        self.low_above_ema = RollingWindow[bool](10)
        self.ema_above_ma = RollingWindow[bool](5)
        self.ma_window = RollingWindow[float](2)
        
    def update(self, trade_bar):
        self.ma.Update(trade_bar.EndTime, trade_bar.Close)
        self.ema.Update(trade_bar.EndTime, trade_bar.Close)
        self.atr.Update(trade_bar)
        self.low_above_ema.Add(self.ema.IsReady and trade_bar.Low > self.ema.Current.Value)
        self.ema_above_ma.Add(self.ema.IsReady and self.ma.IsReady and self.ema.Current.Value > self.ma.Current.Value)
        if self.ma.IsReady:
            self.ma_window.Add(self.ma.Current.Value)
    
    @property
    def ready(self):
        return all((
            self.ma.IsReady,
            self.ema.IsReady,
            self.low_above_ema.IsReady,
            self.ema_above_ma.IsReady,
            self.ma_window.IsReady,
        ))

    @property
    def powertrend_on(self):
        return all(list(self.low_above_ema) + list(self.ema_above_ma)) and self.ma_window[0] > self.ma_window[1]
    
    @property
    def powertrend_off(self):
        return self.ema.Current.Value < self.ma.Current.Value

class Powertrend(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2018, 1, 1)
        self.SetCash(9000)
        self.SetWarmUp(timedelta(50), Resolution.Daily)
        self.EQUITY_RISK_PC = 0.01
        tickers = [
            "SPY",
        ]
        for ticker in tickers:
            self.AddEquity(ticker, Resolution.Daily)
        self.symbol_map = {}

    def OnData(self, data: Slice):
        for symbol in self.ActiveSecurities.Keys:
            if not data.Bars.ContainsKey(symbol):
                return
            if symbol not in self.symbol_map:
                self.symbol_map[symbol] = SymbolIndicators()
            self.symbol_map[symbol].update(data.Bars[symbol])
            if self.IsWarmingUp or not self.symbol_map[symbol].ready:
                continue
            if not self.Portfolio.Invested:
                if data.Bars[symbol].Close > data.Bars[symbol].Open and self.symbol_map[symbol].powertrend_on:
                    self.buy(symbol)
            elif self.symbol_map[symbol].powertrend_off:
                self.Liquidate(symbol)
    
    def buy(self, symbol):
        position_size = (self.Portfolio.TotalPortfolioValue * self.EQUITY_RISK_PC) / self.symbol_map[symbol].atr.Current.Value
        position_value = position_size * self.ActiveSecurities[symbol].Price
        if position_value < self.Portfolio.Cash:
            self.MarketOrder(symbol, position_size)
