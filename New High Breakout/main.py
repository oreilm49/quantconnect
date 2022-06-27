#region imports
from datetime import timedelta

from AlgorithmImports import *
#endregion
from QuantConnect import Resolution
from QuantConnect.Algorithm import QCAlgorithm
from QuantConnect.Brokerages import BrokerageName
from QuantConnect.Indicators import SimpleMovingAverage, RateOfChange, Maximum
from dateutil.parser import parse


class NewHighBreakout(QCAlgorithm):

    def Initialize(self):
        self.SetBrokerageModel(BrokerageName.InteractiveBrokersBrokerage)
        self.SetStartDate(2012, 1, 1)
        self.SetEndDate(2022, 1, 1)
        self.SetCash(10000)
        self.SetWarmUp(200, Resolution.Daily)
        self.UniverseSettings.Resolution = Resolution.Daily
        self.spy = self.AddEquity("SPY", Resolution.Daily)
        self.AddUniverse(self.coarse_selection)
        self.averages = {}
        self._changes = None
        self.EQUITY_RISK_PC = 0.01
        self.open_positions = {}

    def update_spy(self):
        if self.spy.Symbol not in self.averages:
            history = self.History(self.spy.Symbol, 50, Resolution.Daily)
            self.averages[self.spy.Symbol] = SPYSelectionData(history)
        self.averages[self.spy.Symbol].update(self.Time, self.spy.Price)

    def coarse_selection(self, coarse):
        self.update_spy()
        stocks = []
        stock: CoarseFundamental
        coarse = [stock for stock in coarse if stock.Price > 10 and stock.Market == Market.USA and stock.HasFundamentalData]
        for stock in sorted(coarse, key=lambda x: x.DollarVolume, reverse=True)[:100]:
            symbol = stock.Symbol
            if symbol == self.spy.Symbol:
                continue
            if symbol not in self.averages:
                self.averages[symbol] = SelectionData(self.History(symbol, 50, Resolution.Daily))
            self.averages[symbol].update(self.Time, stock)
            if self.averages[symbol].is_ready() and stock.Price > self.averages[symbol].ma.Current.Value:
                stocks.append(symbol)
        return stocks

    @property
    def spy_downtrending(self) -> bool:
        return self.averages[self.spy.Symbol].ma.Current.Value > self.spy.Price

    def position_outdated(self, symbol) -> bool:
        """
        Checks if the position is too old, or if it's time isn't stored
        """
        if self.open_positions.get(symbol):
            return (self.Time - self.open_positions.get(symbol)).days >= 120
        return True

    def OnData(self, slice) -> None:
        if self.IsWarmingUp:
            return
        if self.spy_downtrending:
            for security in self.Portfolio.Securities.keys():
                self.Liquidate(self.Portfolio.Securities[security].Symbol)
            return
        for symbol in self.ActiveSecurities.Keys:
            if symbol == self.spy.Symbol:
                continue
            if self.ActiveSecurities[symbol].Invested:
                if self.Portfolio[symbol].UnrealizedProfitPercent >= 0.20 or \
                    self.Portfolio[symbol].UnrealizedProfitPercent <= -0.08 or \
                        self.ActiveSecurities[symbol].Close < self.averages[symbol].ma.Current.Value or \
                            self.position_outdated(symbol):
                    self.Liquidate(symbol)
            else:
                high = Maximum(100)
                atr = AverageTrueRange(21)
                for data in self.History(symbol, 100, Resolution.Daily).itertuples():
                    if self.Time != data.Index[1]:
                        high.Update(data.Index[1], data.high)
                    atr.Update(
                        TradeBar(data.Index[1], data.Index[0], data.open, data.high, data.low, data.close, data.volume, timedelta(1))
                    )
                if self.ActiveSecurities[symbol].Close >= high.Current.Value:
                    if high.PeriodsSinceMaximum >= 25:
                        position_size = self.calculate_position_size(atr.Current.Value)
                        position_value = position_size * self.ActiveSecurities[symbol].Price
                        if position_value < self.Portfolio.Cash:
                            self.MarketOrder(symbol, position_size)
                            self.open_positions[symbol] = self.Time

    def calculate_position_size(self, atr):
        return round((self.Portfolio.TotalPortfolioValue * self.EQUITY_RISK_PC) / atr)


class SelectionData():
    def __init__(self, history):
        self.roc = RateOfChange(50)
        self.ma = SimpleMovingAverage(50)

        for data in history.itertuples():
            self.roc.Update(data.Index[1], data.close)
            self.ma.Update(data.Index[1], data.close)

    def is_ready(self):
        return self.roc.IsReady and self.ma.IsReady

    def update(self, time, stock):
        self.roc.Update(time, stock.Price)
        self.ma.Update(time, stock.Price)


class SPYSelectionData():
    def __init__(self, history):
        self.ma = SimpleMovingAverage(200)

        for data in history.itertuples():
            self.ma.Update(data.Index[1], data.close)

    def is_ready(self):
        return self.ma.IsReady

    def update(self, time, price):
        self.ma.Update(time, price)
