# region imports
from AlgorithmImports import *
# endregion
from dateutil.parser import parse


class MeanReversionLong(QCAlgorithm):

    def Initialize(self):
        self.SetBrokerageModel(BrokerageName.InteractiveBrokersBrokerage)
        self.SetStartDate(2012, 1, 1)
        self.SetEndDate(2022, 1, 1)
        self.SetCash(10000)
        self.UniverseSettings.Resolution = Resolution.Daily
        self.AddUniverse(self.coarse_selection)
        self.averages = {}
        self._changes = None

    def coarse_selection(self, coarse):
        stocks = []
        for stock in [stock for stock in coarse if stock.DollarVolume > 2500000 and stock.Price > 1]:
            symbol = stock.Symbol
            if symbol not in self.averages:
                self.averages[symbol] = SelectionData(self.History(symbol, 150, Resolution.Daily))
            self.averages[symbol].update(self.Time, stock)
            if self.averages[symbol].is_ready() and stock.Price > self.averages[symbol].ma.Current.Value and \
                    self.averages[symbol].adx.Current.Value >= 45 and \
                    self.averages[symbol].atr.Current.Value >= 0.04 and \
                    self.averages[symbol].rsi.Current.Value <= 30:
                stocks.append(symbol)
        return stocks

    def OnData(self, slice) -> None:
        for symbol in self.ActiveSecurities.Keys:
            if self.ActiveSecurities[symbol].Invested:
                if self.Portfolio[symbol].UnrealizedProfitPercent >= 0.03 or \
                        self.Portfolio[symbol].UnrealizedProfitPercent <= -0.2 or \
                        (self.Time - parse(self.ObjectStore.Read(str(symbol)))).days >= 4:
                    self.Liquidate(symbol)
                    self.ObjectStore.Delete(str(symbol))
            else:
                position_value = self.Portfolio.TotalPortfolioValue / 10
                if position_value < self.Portfolio.Cash:
                    self.MarketOrder(symbol, int(position_value / self.ActiveSecurities[symbol].Price))
                    self.ObjectStore.Save(str(symbol), str(self.Time))

class SelectionData():
    def __init__(self, history):
        self.adx = AverageDirectionalIndex(7)
        self.atr = NormalizedAverageTrueRange(10)
        self.ma = SimpleMovingAverage(150)
        self.rsi = RelativeStrengthIndex(3)

        for data in history.itertuples():
            self.adx.Update(data.Index[1], data.close)
            self.atr.Update(data.Index[1], data.close)
            self.ma.Update(data.Index[1], data.close)
            self.rsi.Update(data.Index[1], data.close)

    def is_ready(self):
        return self.adx.IsReady and self.atr.IsReady and self.ma.IsReady and self.rsi.IsReady

    def update(self, time, stock):
        self.adx.Update(time, stock.Price)
        self.atr.Update(time, stock.Price)
        self.ma.Update(time, stock.Price)
