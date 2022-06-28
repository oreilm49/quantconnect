# region imports
from datetime import timedelta

import pandas as pd
from AlgorithmImports import *
# endregion


class MeanReversionLongETF(QCAlgorithm):
    def Initialize(self):
        self.SetBrokerageModel(BrokerageName.InteractiveBrokersBrokerage)
        self.SetStartDate(2012, 1, 1)
        self.SetEndDate(2022, 1, 1)
        self.SetCash(10000)
        self.UniverseSettings.Resolution = Resolution.Daily
        self.averages = {}
        self._changes = None
        self.EQUITY_RISK_PC = 0.01
        tickers = (
            "XLE", "XLF", "XLU", "XLI", "GDX", "XLK", "XLV", "XLY", "XLP", "XLB", "XOP", "IYR", "XHB", "ITB", "VNQ",
            "GDXJ", "IYE", "OIH", "XME", "XRT", "SMH", "IBB", "KBE", "KRE", "XTL",
        )
        symbols = [Symbol.Create(ticker, SecurityType.Equity, Market.USA) for ticker in tickers]
        self.SetUniverseSelection(ManualUniverseSelectionModel(symbols))
        self.open_positions = {}

    def filter_symbol(self, symbol, data: pd.Series):
        price = self.ActiveSecurities[symbol].Price
        if symbol not in self.averages or self.averages[symbol].is_outdated(self.Time):
            self.averages[symbol] = SymbolData(self.History(symbol, 50, Resolution.Daily), symbol)
        else:
            self.averages[symbol].update(data, self.Time)
        # Rule #1: Stock must be in long term uptrend (above 50 day)
        # Rule #4: 3 day RSI is below 30
        if not (self.averages[symbol].rsi.Current.Value < 30 and price > self.averages[symbol].ma.Current.Value):
            return
        # Rule #2: 7 day ADX above 45 (strong short term trend)
        if not self.averages[symbol].adx.Current.Value > 45:
            return
        natr = self.averages[symbol].atr.Current.Value / self.ActiveSecurities[symbol].Price
        # Rule #3: ATR% above 4
        if natr < 0.04:
            return
        return symbol

    def position_outdated(self, symbol) -> bool:
        """
        Checks if the position is too old, or if it's time isn't stored
        """
        if self.open_positions.get(symbol):
            return (self.Time - self.open_positions.get(symbol)).days >= 4
        return True

    def OnData(self, slice) -> None:
        tradeable = []
        for symbol in self.ActiveSecurities.Keys:
            if self.ActiveSecurities[symbol].Invested:
                if self.Portfolio[symbol].UnrealizedProfitPercent >= 0.03 or \
                    self.Portfolio[symbol].UnrealizedProfitPercent <= -0.2 or \
                        self.position_outdated(symbol):
                    self.Liquidate(symbol)
            elif slice.Bars.ContainsKey(symbol) and self.filter_symbol(symbol, slice.Bars.get(symbol)):
                tradeable.append(symbol)
        for symbol in sorted(tradeable, key=lambda x: self.averages[x].rsi.Current.Value):
            position_size, position_value = self.calculate_position(symbol, self.averages[symbol].atr.Current.Value)
            if self.Portfolio.GetMarginRemaining(symbol, OrderDirection.Buy) > position_value:
                self.MarketOrder(symbol, position_size)
                self.open_positions[symbol] = self.Time

    def calculate_position(self, symbol, atr):
        position_size = round((self.Portfolio.TotalPortfolioValue * self.EQUITY_RISK_PC) / atr)
        return position_size, position_size * self.ActiveSecurities[symbol].Price


class SymbolData():
    def __init__(self, history, symbol):
        self.adx = AverageDirectionalIndex(7)
        self.atr = AverageTrueRange(10)
        self.ma = SimpleMovingAverage(50)
        self.rsi = RelativeStrengthIndex(3)
        self.symbol = symbol
        self.time = None

        for data in history.itertuples():
            self.update(data)

    def update(self, data, time=None):
        time = time or data.Index[1]
        trade_bar = TradeBar(time, self.symbol, data.open, data.high, data.low, data.close, data.volume, timedelta(1))
        self.adx.Update(trade_bar)
        self.atr.Update(trade_bar)
        self.rsi.Update(time, data.close)
        self.ma.Update(time, data.close)
        self.time = time

    def is_outdated(self, time):
        return (time - self.ma.Current.Time).days > 1
