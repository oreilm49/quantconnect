#region imports
from AlgorithmImports import *
#endregion


class RocRotation(QCAlgorithm):

    def Initialize(self):
        self.SetBrokerageModel(BrokerageName.InteractiveBrokersBrokerage)
        self.SetStartDate(2012, 1, 1)
        self.SetEndDate(2022, 1, 1)
        self.SetCash(10000)
        self.UniverseSettings.Resolution = Resolution.Daily
        self.spy = self.AddEquity("SPY", Resolution.Daily)
        self.SetBenchmark("SPY")
        self.AddUniverse(self.coarse_selection)
        self.averages = {}
        self._changes = None

    def update_spy(self):
        if self.spy.Symbol not in self.averages:
            history = self.History(self.spy.Symbol, 200, Resolution.Daily)
            self.averages[self.spy.Symbol] = SPYSelectionData(history)
        self.averages[self.spy.Symbol].update(self.Time, self.spy.Price)

    def coarse_selection(self, coarse):
        self.update_spy()
        stocks = []
        for stock in sorted(coarse, key=lambda x: x.DollarVolume, reverse=True)[:100]:
            symbol = stock.Symbol
            if symbol == self.spy.Symbol:
                continue
            if symbol not in self.averages:
                self.averages[symbol] = SelectionData(self.History(symbol, 200, Resolution.Daily))
            self.averages[symbol].update(self.Time, stock.Price)
            stocks.append(symbol)
        return sorted(stocks, key=lambda symbol: self.averages[symbol].roc, reverse=True)[:10]

    @property
    def spy_downtrending(self) -> bool:
        return self.averages[self.spy.Symbol].ma.Current.Value * .98 > self.spy.Price

    def OnData(self, data):
        if self.spy_downtrending:
            for security in self.Portfolio.Securities.keys():
                self.Liquidate(self.Portfolio.Securities[security].Symbol)
            return
        if not self.is_tuesday():
            return
        # if we have no changes, do nothing
        if self._changes is None: return
        # liquidate removed securities
        for security in self._changes.RemovedSecurities:
            if security.Invested:
                self.Liquidate(security.Symbol)
        for symbol in self.ActiveSecurities.Keys:
            if symbol == self.spy.Symbol:
                continue
            if self.ActiveSecurities[symbol].Invested:
                continue
            if not self.ActiveSecurities[symbol].Price > self.averages[symbol].ma.Current.Value:
                continue
            if not self.averages[symbol].rsi.Current.Value < 50:
                continue
            position_value = self.Portfolio.TotalPortfolioValue / 10
            if position_value < self.Portfolio.Cash:
                self.MarketOrder(symbol, int(position_value / self.ActiveSecurities[symbol].Price))
        self._changes = None

    def OnSecuritiesChanged(self, changes):
        self._changes = changes

    def is_tuesday(self):
        return self.Time.weekday() == 1


class SelectionData():
    def __init__(self, history):
        self.rsi = RelativeStrengthIndex(3)
        self.roc = RateOfChangePercent(200)
        self.ma = SimpleMovingAverage(200)

        for data in history.itertuples():
            self.rsi.Update(data.Index[1], data.close)
            self.roc.Update(data.Index[1], data.close)
            self.ma.Update(data.Index[1], data.close)

    def is_ready(self):
        return self.rsi.IsReady and self.roc.IsReady and self.ma.IsReady

    def update(self, time, price):
        self.rsi.Update(time, price)
        self.roc.Update(time, price)
        self.ma.Update(time, price)


class SPYSelectionData():
    def __init__(self, history):
        self.ma = SimpleMovingAverage(200)

        for data in history.itertuples():
            self.ma.Update(data.Index[1], data.close)

    def is_ready(self):
        return self.ma.IsReady

    def update(self, time, price):
        self.ma.Update(time, price)
