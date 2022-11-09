from AlgorithmImports import *


class MomentumETF(QCAlgorithm):
    def Initialize(self):
        self.SetStartDate(2019, 1, 1)  # Set Start Date
        self.SetEndDate(2020, 1, 1)  # Set End Date
        self.SetCash(100000)  # Set Strategy Cash
        tickers = ['SPY']
        self.symbol_map = {}
        self.EnableAutomaticIndicatorWarmUp = True
        for ticker in tickers:
            symbol = self.AddEquity(ticker, Resolution.Daily).Symbol
            self.symbol_map[symbol] = {
                'bollinger': self.BB(symbol, 21),
                'keltner': self.KCH(symbol, 21),
                'donchian': self.DCH(symbol, 21),
                'mfi': self.MFI(symbol, 5),
                'atr': self.ATR(symbol, 21),
            }

    def OnData(self, slice):
        uninvested = []
        for symbol in self.ActiveSecurities.Keys:
            if symbol.Value not in self.symbol_map:
                continue
            if not self.ActiveSecurities[symbol].Invested:
                uninvested.append(symbol)
            highest_lower_band = min((
                self.symbol_map[symbol]['bollinger'].LowerBand.Current.Value,
                self.symbol_map[symbol]['keltner'].LowerBand.Current.Value,
                self.symbol_map[symbol]['donchian'].LowerBand.Current.Value,
            ))
            mfi_oversold = self.symbol_map[symbol]['mfi'].Current.Value >= 80
            if slice.Bars[symbol].Low <= highest_lower_band and mfi_oversold:
                self.Liquidate(symbol)
        uninvested = sorted(
            uninvested, 
            key=lambda symbol: self.symbol_map[symbol]['mfi'].Current.Value, 
            reverse=True,
        )
        for symbol in uninvested:
            lowest_upper_band = min((
                self.symbol_map[symbol]['bollinger'].UpperBand.Current.Value,
                self.symbol_map[symbol]['keltner'].UpperBand.Current.Value,
                self.symbol_map[symbol]['donchian'].UpperBand.Current.Value,
            ))
            mfi_overbought = self.symbol_map[symbol]['mfi'].Current.Value >= 80
            if slice.Bars[symbol].High >= lowest_upper_band and mfi_overbought:
                position_size = self.calculate_position_size(self.symbol_map[symbol]['atr'].Current.Value)
                position_value = position_size * self.ActiveSecurities[symbol].Price
                if position_value < self.Portfolio.Cash:
                    self.MarketOrder(symbol, position_size)
    
    def calculate_position_size(self, atr):
        return round((self.Portfolio.TotalPortfolioValue * self.EQUITY_RISK_PC) / atr)
