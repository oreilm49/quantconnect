# region imports
from datetime import timedelta

from AlgorithmImports import *
# endregion
from dateutil.parser import parse


class MeanReversionLong(QCAlgorithm):
    def Initialize(self):
        self.SetBrokerageModel(BrokerageName.InteractiveBrokersBrokerage)
        self.SetStartDate(2012, 1, 1)
        self.SetEndDate(2022, 2, 1)
        self.SetCash(10000)
        self.UniverseSettings.Resolution = Resolution.Daily
        self.AddUniverse(self.coarse_selection)
        self.symbol_data = {}
        self.EQUITY_RISK_PC = 0.01
        self.STOP_LOSS_PC = 0.08

    def coarse_selection(self, coarse):
        stocks = []
        coarse = sorted(
            [stock for stock in coarse if stock.DollarVolume > 2500000 and stock.Price > 1 and stock.Market == Market.USA and stock.HasFundamentalData],
            key=lambda x: x.DollarVolume, reverse=True
        )[:500]
        for stock in coarse:
            symbol = stock.Symbol
            if symbol not in self.symbol_data:
                self.symbol_data[symbol] = SymbolData(self.History(stock.Symbol, 200, Resolution.Daily))
            else:
                self.symbol_data[symbol].update(self.Time, stock.Price)
            # Rule #1: Trend template
            if not (stock.Price > self.symbol_data[symbol].ma.Current.Value >
                    self.symbol_data[symbol].ma_long.Current.Value > self.symbol_data[symbol].ma_200.Current.Value):
                continue
            # Rule #2: 7 day ROC greater than 0
            if self.symbol_data[symbol].roc.Current.Value < 0:
                continue
            # Rule #3: 2 day RSI less than 30
            if self.symbol_data[symbol].rsi.Current.Value > 30:
                continue
            stocks.append(stock)
        # Rule #3: Rank by the lowest RSI = most oversold stocks
        symbols = [stock.Symbol for stock in sorted(stocks, key=lambda x: self.symbol_data[x.Symbol].roc.Current.Value, reverse=True)]
        return symbols

    def position_outdated(self, symbol) -> bool:
        """
        Checks if the position is too old, or if it's time isn't stored
        """
        if self.ObjectStore.ContainsKey(str(symbol)):
            return (self.Time - parse(self.ObjectStore.Read(str(symbol)))).days >= 4
        return True

    def OnData(self, slice) -> None:
        for symbol in self.ActiveSecurities.Keys:
            if self.ActiveSecurities[symbol].Invested:
                if self.Portfolio[symbol].UnrealizedProfitPercent >= 0.03 or \
                    self.Portfolio[symbol].UnrealizedProfitPercent <= self.STOP_LOSS_PC * -1 or \
                        self.position_outdated(symbol):
                    self.Liquidate(symbol)
                    if self.ObjectStore.ContainsKey(str(symbol)):
                        self.ObjectStore.Delete(str(symbol))
            else:
                position_size, position_value = self.calculate_position(symbol)
                if position_size > 0 and self.Portfolio.GetMarginRemaining(symbol, OrderDirection.Buy) > position_value:
                    self.MarketOrder(symbol, position_size)
                    self.ObjectStore.Save(str(symbol), str(self.Time))

    def calculate_position(self, symbol):
        risk = self.ActiveSecurities[symbol].Price * self.STOP_LOSS_PC
        if risk <= 0:
            return 0, 0
        size = int((self.Portfolio.TotalPortfolioValue * self.EQUITY_RISK_PC) / risk)
        return size, size * self.ActiveSecurities[symbol].Price


class SymbolData:
    def __init__(self, history):
        self.rsi = RelativeStrengthIndex(2)
        self.ma = SimpleMovingAverage(50)
        self.ma_long = SimpleMovingAverage(150)
        self.ma_200 = SimpleMovingAverage(200)
        self.roc = RateOfChangePercent(7)

        for data in history.itertuples():
            self.update(data.Index[1], data.close)

    def update(self, time, price):
        self.rsi.Update(time, price)
        self.ma.Update(time, price)
        self.ma_long.Update(time, price)
        self.ma_200.Update(time, price)
        self.roc.Update(time, price)
