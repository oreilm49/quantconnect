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
    
    @property
    def ma_above_ma_long(self):
        return 1 - self.ma_long.Current.Value/self.ma.Current.Value
    
    @property
    def ma_violated(self):
        return self.closed_below_window[1] and self.closed_below_window[0]

class MABreakthroughETF(QCAlgorithm):

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
        self.warm_up_buy_signals = set()
        for ticker in tickers:
            self.AddEquity(ticker, Resolution.Daily)

    def live_log(self, msg):
        if self.LiveMode:
            self.Log(msg)

    def OnData(self, data):
        uninvested = []
        self.Debug(f"{self.Time} - {','.join([symbol.Value for symbol in self.warm_up_buy_signals])}")
        for symbol in self.ActiveSecurities.Keys:
            if not data.Bars.ContainsKey(symbol):
                self.Debug("symbol not in data")
                continue
            if symbol not in self.symbol_map:
                self.symbol_map[symbol] = SymbolIndicators()
            self.symbol_map[symbol].update(data.Bars[symbol])
            if not self.symbol_map[symbol].ready:
                self.Debug("indicators not ready")
                continue
            if not self.ActiveSecurities[symbol].Invested:
                uninvested.append(symbol)
                if symbol in self.warm_up_buy_signals and self.sell_signal(symbol, data):
                    self.Debug(f"removing warmed up buy signal: {symbol.Value}")
                    self.warm_up_buy_signals.remove(symbol)
            elif self.sell_signal(symbol, data):
                self.Liquidate(symbol)
        uninvested = sorted(
            uninvested, 
            key=lambda symbol: self.symbol_map[symbol].ma_above_ma_long, 
            reverse=True,
        )
        for symbol in uninvested:
            if symbol in self.warm_up_buy_signals:
                self.Debug(f"buying warmed up symbol: {symbol.Value}")
                self.buy(symbol)
                continue
            close = data.Bars[symbol].Close
            ma = self.symbol_map[symbol].ma.Current.Value
            ma_long = self.symbol_map[symbol].ma_long.Current.Value
            prev_close_below_ma = self.symbol_map[symbol].closed_below_window[1]
            if not self.ActiveSecurities[symbol].Invested:
                if ma > ma_long:
                    if prev_close_below_ma and close > ma:
                        self.buy(symbol)
    
    def buy(self, symbol):
        if self.IsWarmingUp:
            self.Debug(f"adding symbol to warm  up signals: {symbol.Value}")
            self.warm_up_buy_signals.add(symbol)
        else:
            position_size = round((self.Portfolio.TotalPortfolioValue * self.EQUITY_RISK_PC) / self.symbol_map[symbol].atr.Current.Value)
            position_value = position_size * self.ActiveSecurities[symbol].Price
            self.live_log(f"buying {symbol.Value}")
            if position_value < self.Portfolio.Cash:
                self.MarketOrder(symbol, position_size)
                if symbol in self.warm_up_buy_signals:
                    self.warm_up_buy_signals.remove(symbol)
                    self.Debug(f"symbol purchased and removed from warm up signals: {symbol.Value}")
            else:
                self.live_log(f"insufficient cash ({self.Portfolio.Cash}) to purchase {symbol.Value}")
    
    def sell_signal(self, symbol, data):
        ma = self.symbol_map[symbol].ma.Current.Value
        ma_long = self.symbol_map[symbol].ma_long.Current.Value
        return self.symbol_map[symbol].ma_violated or ma_long > ma or ma_long > data.Bars[symbol].Close

