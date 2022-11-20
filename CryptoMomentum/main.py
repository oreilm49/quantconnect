# region imports
from AlgorithmImports import *
# endregion

class SymbolIndicators:
    def __init__(self) -> None:
        self.ma = SimpleMovingAverage(50)
        self.ma_long = SimpleMovingAverage(200)
        self.atr = AverageTrueRange(21)
        self.closed_below_window = RollingWindow[bool](2)
        
    def update(self, trade_bar):
        self.ma.Update(trade_bar.EndTime, trade_bar.Close)
        self.ma_long.Update(trade_bar.EndTime, trade_bar.Close)
        self.atr.Update(trade_bar)
        if self.ma.IsReady and self.ma.Current.Value > trade_bar.Close:
            self.closed_below_window.Add(True)
        else:
            self.closed_below_window.Add(False)
    
    @property
    def ready(self):
        return all((
            self.ma.IsReady,
            self.ma_long.IsReady,
            self.closed_below_window.IsReady,
        ))

class CryptoMomentum(QCAlgorithm):

    def Initialize(self):
        resolution = Resolution.Daily
        self.SetBrokerageModel(BrokerageName.Binance, AccountType.Cash)
        self.SetStartDate(2018, 1, 1)
        self.SetCash('USDT', 9000)
        self.SetWarmUp(timedelta(200), resolution)
        self.EQUITY_RISK_PC = 0.01
        tickers = [
            "BTCUSDT",
            "ETHUSDT",
        ]
        for ticker in tickers:
            symbol = self.AddCrypto(ticker, resolution, Market.Binance).Symbol
            trade_plot = Chart(f'Trade Plot {symbol.Value}')
            trade_plot.AddSeries(Series('Longs', SeriesType.Scatter, "", Color.Green, ScatterMarkerSymbol.Triangle))
            self.AddChart(trade_plot)
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
            ma = self.symbol_map[symbol].ma.Current.Value
            ma_long = self.symbol_map[symbol].ma_long.Current.Value
            prev_close_below_ma = self.symbol_map[symbol].closed_below_window[1]
            if not self.ActiveSecurities[symbol].Invested:
                if ma > ma_long:
                    if prev_close_below_ma and close > ma:
                        self.buy(symbol)
                        self.Plot(f'Trade Plot {symbol.Value}', "Longs", close)
            elif close < ma or ma_long > ma or ma_long > close:
                self.Liquidate(symbol)
    
    def buy(self, symbol):
        position_size = (self.Portfolio.TotalPortfolioValue * self.EQUITY_RISK_PC) / self.symbol_map[symbol].atr.Current.Value
        position_value = position_size * self.ActiveSecurities[symbol].Price
        if position_value < self.Portfolio.Cash:
            self.MarketOrder(symbol, position_size)
