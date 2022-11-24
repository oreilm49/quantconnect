# region imports
from AlgorithmImports import *
# endregion

class SymbolIndicators:
    def __init__(self) -> None:
        self.roc = RateOfChangePercent(50)
        self.atr = AverageTrueRange(21)
        self.ma = SimpleMovingAverage(50)
        
    def update(self, trade_bar):
        self.roc.Update(trade_bar.EndTime, trade_bar.Close)
        self.atr.Update(trade_bar)
        self.ma.Update(trade_bar.EndTime, trade_bar.Close)
    
    @property
    def ready(self):
        return all((
            self.roc.IsReady,
            self.atr.IsReady,
            self.ma.IsReady,
        ))


class RateOfChangeRotationETF(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2002, 1, 1)
        self.SetEndDate(2022, 11, 1)
        self.SetCash(10000)
        self.SetWarmUp(timedelta(200), Resolution.Daily)
        self.UniverseSettings.Resolution = Resolution.Daily
        self.SetBrokerageModel(BrokerageName.InteractiveBrokersBrokerage)
        self.EQUITY_RISK_PC = 0.01
        tickers = [
            "GXLE",
            "GXLK",
            "GXLV",
            "GXLF",
            "SXLP",
            "SXLI",
            "GXLC",
            "SXLY",
            "SXLB",
            "SXLU",
        ] if self.LiveMode else [
            "XLE",
            "XLK",
            "XLV",
            "XLF",
            "XLP",
            "XLI",
            "XLC",
            "XLY",
            "XLB",
            "XLU",
        ]
        self.symbol_map = {}
        for ticker in tickers:
            self.AddEquity(ticker, Resolution.Daily)

    def live_log(self, msg):
        if self.LiveMode:
            self.Log(msg)

    def OnData(self, data):
        invested = []
        symbols = []
        for symbol in self.ActiveSecurities.Keys:
            if not data.Bars.ContainsKey(symbol):
                self.Debug("symbol not in data")
                continue
            if symbol not in self.symbol_map:
                self.symbol_map[symbol] = SymbolIndicators()
            self.symbol_map[symbol].update(data.Bars[symbol])
            if not self.symbol_map[symbol].ready or data.Bars[symbol].Close < self.symbol_map[symbol].ma.Current.Value:
                continue
            symbols.append(symbol)
            if self.ActiveSecurities[symbol].Invested:
                invested.append(symbol)
        if self.IsWarmingUp:
            return
        highest_roc = sorted(
            symbols, 
            key=lambda symbol: self.symbol_map[symbol].roc, 
            reverse=True,
        )[:5]
        for symbol in highest_roc:
            if not self.ActiveSecurities[symbol].Invested:
                self.buy(symbol)
                invested.append(symbol)
        for symbol in invested:
            if symbol not in highest_roc or data.Bars[symbol].Close < self.symbol_map[symbol].ma.Current.Value:
                self.Liquidate(symbol)
    
    def buy(self, symbol):
        position_size = round((self.Portfolio.TotalPortfolioValue * self.EQUITY_RISK_PC) / self.symbol_map[symbol].atr.Current.Value)
        position_value = position_size * self.ActiveSecurities[symbol].Price
        self.live_log(f"buying {symbol.Value}")
        if position_value < self.Portfolio.Cash:
            self.MarketOrder(symbol, position_size)
        else:
            self.live_log(f"insufficient cash ({self.Portfolio.Cash}) to purchase {symbol.Value}")
    
    def sell_signal(self, symbol, data):
        ma = self.symbol_map[symbol].ma.Current.Value
        ma_long = self.symbol_map[symbol].ma_long.Current.Value
        return self.symbol_map[symbol].ma_violated or ma_long > ma or ma_long > data.Bars[symbol].Close

