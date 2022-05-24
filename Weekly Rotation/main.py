from QuantConnect import Resolution
from QuantConnect.Algorithm import QCAlgorithm
from QuantConnect.Indicators import RelativeStrengthIndex, RateOfChange, SimpleMovingAverage


class WeeklyRotation(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2021, 1, 1)
        self.SetEndDate(2022, 1, 1)
        self.SetCash(10000)
        self.UniverseSettings.Resolution = Resolution.Daily
        self.spy = self.AddEquity("SPY", Resolution.Daily)
        self.AddUniverse(self.coarse_selection)
        self.averages = {}
        self._changes = None

    def update_spy(self):
        history = self.History(self.spy.Symbol, 200, Resolution.Daily)
        self.averages[self.spy.Symbol] = SPYSelectionData(history)
        self.averages[self.spy.Symbol].update(self.Time, self.spy.Price)

    def coarse_selection(self, coarse):
        self.update_spy()
        stocks = []
        for stock in sorted(coarse, key=lambda x: x.DollarVolume, reverse=True)[:100]:
            symbol = stock.Symbol
            if symbol not in self.averages and symbol != self.spy.Symbol:
                history = self.History(symbol, 200, Resolution.Daily)
                self.averages[symbol] = SelectionData(history)
                self.averages[symbol].update(self.Time, stock.Price)
                stocks.append(stock)
        stocks = sorted(stocks, key=lambda stock: self.averages[stock.Symbol].roc, reverse=True)[:10]
        return [stock.Symbol for stock in stocks]

    @property
    def spy_downtrending(self) -> bool:
        return self.averages[self.spy.Symbol].ma_200.Current.Value > self.spy.Price

    def OnData(self, data):
        if self.spy_downtrending:
            for security in self.Portfolio.Securities.keys():
                self.Liquidate(self.Portfolio.Securities[security].Symbol)
            return
        # if we have no changes, do nothing
        if self._changes is None: return
        # liquidate removed securities
        for security in self._changes.RemovedSecurities:
            if security.Invested:
                self.Liquidate(security.Symbol)
        for symbol in self.ActiveSecurities.Keys:
            if symbol != self.spy.Symbol and not self.ActiveSecurities[symbol].Invested and \
                    self.averages[symbol].is_ready() and self.averages[symbol].rsi.Current.Value < 50:
                self.SetHoldings(symbol, 0.1)
        self._changes = None

    def OnSecuritiesChanged(self, changes):
        self._changes = changes


class SelectionData():
    def __init__(self, history):
        self.rsi = RelativeStrengthIndex(3)
        self.roc = RateOfChange(200)

        for data in history.itertuples():
            self.rsi.Update(data.Index[1], data.close)
            self.roc.Update(data.Index[1], data.close)

    def is_ready(self):
        return self.rsi.IsReady and self.roc.IsReady

    def update(self, time, price):
        self.rsi.Update(time, price)
        self.roc.Update(time, price)


class SPYSelectionData():
    def __init__(self, history):
        self.ma_200 = SimpleMovingAverage(200)

        for data in history.itertuples():
            self.ma_200.Update(data.Index[1], data.close)

    def is_ready(self):
        return self.ma_200.IsReady

    def update(self, time, price):
        self.ma_200.Update(time, price)
