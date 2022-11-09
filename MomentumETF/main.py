from AlgorithmImports import *


class SymbolIndicators:
    def __init__(self, bollinger, keltner, donchian, mfi, atr) -> None:
        self.bollinger = bollinger
        self.keltner = keltner
        self.donchian = donchian
        self.mfi = mfi
        self.atr = atr
    
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
        self.SetStartDate(2019, 1, 1)
        self.SetEndDate(2020, 1, 1)
        self.SetCash(100000)
        self.UniverseSettings.Resolution = Resolution.Daily
        self.SetWarmUp(21, Resolution.Daily)
        tickers = ['AAPL']
        self.symbol_map = {}
        self.EnableAutomaticIndicatorWarmUp = True
        for ticker in tickers:
            symbol = self.AddEquity(ticker).Symbol
            self.symbol_map[symbol] = SymbolIndicators(
                self.BB(symbol, 21, 2),
                self.KCH(symbol, 21, 2),
                self.DCH(symbol, 21, 2),
                self.MFI(symbol, 5),
                self.ATR(symbol, 21),
            )

    def OnData(self, slice):
        self.Debug(self.Time)
        if self.IsWarmingUp:
            return
        uninvested = []
        for symbol in self.ActiveSecurities.Keys:
            if symbol not in self.symbol_map:
                continue
            if not self.symbol_map[symbol].ready:
                self.Debug("indicators not ready")
                continue
            if not slice.ContainsKey(symbol):
                self.Debug("symbol not in slice")
                continue
            if not self.ActiveSecurities[symbol].Invested:
                uninvested.append(symbol)
            else:
                highest_lower_band = self.symbol_map[symbol].highest_lower_band
                mfi_oversold = self.symbol_map[symbol].mfi.Current.Value <= 20
                if slice.Bars[symbol].Low <= highest_lower_band and mfi_oversold:
                    self.Liquidate(symbol)
        uninvested = sorted(
            uninvested, 
            key=lambda symbol: self.symbol_map[symbol].mfi.Current.Value, 
            reverse=True,
        )
        for symbol in uninvested:
            if not self.symbol_map[symbol].mfi.Current.Value >= 80:
                continue
            self.Debug(f"overbought: {self.ActiveSecurities[symbol].Price} {self.symbol_map[symbol].lowest_upper_band}")
            if self.ActiveSecurities[symbol].Price >= self.symbol_map[symbol].lowest_upper_band:
                position_size = self.calculate_position_size(self.symbol_map[symbol].atr.Current.Value)
                position_value = position_size * self.ActiveSecurities[symbol].Price
                if position_value < self.Portfolio.Cash:
                    self.MarketOrder(symbol, position_size)
    
    def calculate_position_size(self, atr):
        return round((self.Portfolio.TotalPortfolioValue * self.EQUITY_RISK_PC) / atr)
