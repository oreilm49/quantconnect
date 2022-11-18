# region imports
from AlgorithmImports import *
# endregion

class SymbolIndicators:
    def __init__(self) -> None:
        self.ma = SimpleMovingAverage(50)
        self.ema = ExponentialMovingAverage(21)
        self.atr = AverageTrueRange(21)
        self.ema_window = RollingWindow[int](3)
        
    def update(self, trade_bar):
        self.ma.Update(trade_bar.EndTime, trade_bar.Close)
        self.ema.Update(trade_bar.EndTime, trade_bar.Close)
        self.atr.Update(trade_bar)
        if self.ema.IsReady:
            self.ema_window.Add(self.ema.Current.Value)
    
    @property
    def ready(self):
        return all((
            self.ma.IsReady,
            self.ema.IsReady,
            self.ema_window.IsReady,
        ))

class CryptoMomentum(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2018, 1, 1)
        self.SetCash(9000)
        self.SetWarmUp(timedelta(50), Resolution.Daily)
        self.EQUITY_RISK_PC = 0.01
        tickers = [
            "BTCUSD",
        ]
        for ticker in tickers:
            self.AddCrypto(ticker, Resolution.Daily)
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
            close = data.Bars[symbol].Close
            ema = self.symbol_map[symbol].ema.Current.Value
            ma = self.symbol_map[symbol].ma.Current.Value
            ema_vals = list(reversed(list(self.symbol_map[symbol].ema_window)))
            ema_increasing = all(prev_val < next_val for prev_val, next_val in zip(ema_vals, ema_vals[1:]))
            if not self.Portfolio.Invested:
                if close > ema:
                    if ema_increasing:
                        if ema > ma:
                            self.buy(symbol)
            elif close < ema or not ema_increasing or ema < ma:
                self.Liquidate()
    
    def buy(self, symbol):
        position_size = (self.Portfolio.TotalPortfolioValue * self.EQUITY_RISK_PC) / self.symbol_map[symbol].atr.Current.Value
        position_value = position_size * self.ActiveSecurities[symbol].Price
        if position_value < self.Portfolio.Cash:
            self.MarketOrder(symbol, position_size)
