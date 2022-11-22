from AlgorithmImports import *
from datetime import timedelta


class SymbolIndicators:
    def __init__(self, history) -> None:
        self.bollinger = BollingerBands(21, 2)
        self.keltner = KeltnerChannels(21, 2)
        self.donchian = DonchianChannel(21, 2)
        self.mfi = MoneyFlowIndex(5)
        self.atr = AverageTrueRange(21)

        for data in history.itertuples():
            trade_bar = TradeBar(data.Index[1], data.Index[0], data.open, data.high, data.low, data.close, data.volume, timedelta(1))
            self.update(trade_bar)
        
    def update(self, trade_bar):
        self.bollinger.Update(trade_bar.EndTime, trade_bar.Close)
        self.keltner.Update(trade_bar)
        self.donchian.Update(trade_bar)
        self.mfi.Update(trade_bar)
        self.atr.Update(trade_bar)
    
    @property
    def ready(self):
        return all((
            self.bollinger.IsReady,
            self.keltner.IsReady,
            self.donchian.IsReady,
            self.mfi.IsReady,
            self.atr.IsReady,
        ))
    
    @property
    def lowest_upper_band(self):
        return min((
            self.bollinger.UpperBand.Current.Value,
            self.keltner.UpperBand.Current.Value,
            self.donchian.UpperBand.Current.Value,
        ))
    
    @property
    def highest_lower_band(self):
        return max((
            self.bollinger.LowerBand.Current.Value,
            self.keltner.LowerBand.Current.Value,
            self.donchian.LowerBand.Current.Value,
        ))


class MomentumETF(QCAlgorithm):
    def Initialize(self):
        self.SetStartDate(2002, 1, 1)
        self.SetEndDate(2022, 11, 1)
        self.SetCash(10000)
        self.SetWarmUp(timedelta(21), Resolution.Daily)
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
                self.symbol_map[symbol] = SymbolIndicators(
                    self.History(symbol, 21, Resolution.Daily)
                )
            else:
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
            key=lambda symbol: self.symbol_map[symbol].mfi.Current.Value, 
            reverse=True,
        )
        for symbol in uninvested:
            if symbol in self.warm_up_buy_signals:
                self.Debug(f"buying warmed up symbol: {symbol.Value}")
                self.buy(symbol)
                continue
            if not self.symbol_map[symbol].mfi.Current.Value >= 80:
                continue
            self.Debug(f"overbought: {self.ActiveSecurities[symbol].Price} {self.symbol_map[symbol].lowest_upper_band}")
            if self.ActiveSecurities[symbol].Price >= self.symbol_map[symbol].lowest_upper_band:
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
    
    def sell_signal(self, symbol, slice):
        highest_lower_band = self.symbol_map[symbol].highest_lower_band
        mfi_oversold = self.symbol_map[symbol].mfi.Current.Value <= 20
        return slice.Bars[symbol].Low <= highest_lower_band and mfi_oversold
