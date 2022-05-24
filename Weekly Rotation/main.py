from QuantConnect import Resolution
from QuantConnect.Algorithm import QCAlgorithm
from QuantConnect.Indicators import RelativeStrengthIndex, RateOfChange, SimpleMovingAverage, ExponentialMovingAverage, \
    RollingWindow, IndicatorDataPoint


class WeeklyRotation(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2002, 1, 1)
        self.SetEndDate(2022, 1, 1)
        self.SetCash(10000)
        self.UniverseSettings.Resolution = Resolution.Daily
        self.spy = self.AddEquity("SPY", Resolution.Daily)
        self.AddUniverse(self.coarse_selection, self.fine_selection)
        self.averages = {}
        self._changes = None

    def update_spy(self):
        history = self.History(self.spy.Symbol, 200, Resolution.Daily)
        self.averages[self.spy.Symbol] = SPYSelectionData(history)
        self.averages[self.spy.Symbol].update(self.Time, self.spy.Price)

    def coarse_selection(self, coarse):
        self.update_spy()
        MIN_VOL = 1000000
        MIN_PRICE = 1
        return [stock.Symbol for stock in coarse if stock.Volume > MIN_VOL and stock.Price > MIN_PRICE]

    def fine_selection(self, fine):
        """
        S&P500 stocks (market cap > $15bn)
        Min price $1
        Min vol 1,000,000
        Top 10 ROC stocks
        """
        MIN_MTKCAP = 15000000000
        selected = []
        for stock in fine:
            if not (stock.MarketCap > MIN_MTKCAP):
                continue
            selected.append(stock)
            symbol = stock.Symbol
            if symbol not in self.averages:
                # 1. Call history to get an array of 200 days of history data
                history = self.History(symbol, 200, Resolution.Daily)
                #2. Adjust SelectionData to pass in the history result
                self.averages[symbol] = SelectionData(history)
                self.averages[symbol].update(self.Time, stock.Price)
        selected = sorted(selected, key=lambda stock: self.averages[stock.Symbol].roc, reverse=True)[0:10]
        return [stock.Symbol for stock in selected]

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
                    self.averages[symbol].is_ready() and self.averages[symbol].rsi.Current.Value < 50\
                    and self.averages[symbol].ema_increasing:
                self.SetHoldings(symbol, 0.1)
        self._changes = None

    def OnSecuritiesChanged(self, changes):
        self._changes = changes


class SelectionData():
    def __init__(self, history):
        self.rsi = RelativeStrengthIndex(3)
        self.roc = RateOfChange(200)
        self.ema_21 = ExponentialMovingAverage(21)
        self.ema_window = RollingWindow[IndicatorDataPoint](3)
        self.ema_21.Updated += self.ema_updated

        for data in history.itertuples():
            self.rsi.Update(data.Index[1], data.close)
            self.roc.Update(data.Index[1], data.close)
            self.ema_21.Update(data.Index[1], data.close)

    def is_ready(self):
        return self.rsi.IsReady and self.roc.IsReady

    def update(self, time, price):
        self.rsi.Update(time, price)
        self.roc.Update(time, price)
        self.ema_21.Update(time, price)

    def ema_updated(self, sender, updated):
        self.ema_window.Add(updated)

    @property
    def ema_increasing(self):
        return self.ema_window[0] > self.ema_window[2]


class SPYSelectionData():
    def __init__(self, history):
        self.ma_200 = SimpleMovingAverage(200)

        for data in history.itertuples():
            self.ma_200.Update(data.Index[1], data.close)

    def is_ready(self):
        return self.ma_200.IsReady

    def update(self, time, price):
        self.ma_200.Update(time, price)
