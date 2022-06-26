#region imports
from datetime import timedelta

from AlgorithmImports import *
#endregion


class NewHighBreakout(QCAlgorithm):

    def Initialize(self):
        self.SetBrokerageModel(BrokerageName.InteractiveBrokersBrokerage)
        self.SetStartDate(2012, 1, 1)
        self.SetEndDate(2022, 1, 1)
        self.SetCash(10000)
        self.UniverseSettings.Resolution = Resolution.Daily
        self.spy = self.AddEquity("SPY", Resolution.Daily)
        self.AddUniverse(self.coarse_selection)
        self.averages = {}
        self._changes = None
        self.EQUITY_RISK_PC = 0.01
        self.STOP_LOSS_PC = 0.08
        self.open_positions = {}

    def update_spy(self):
        if self.spy.Symbol not in self.averages:
            self.averages[self.spy.Symbol] = SPYSelectionData(self.History(self.spy.Symbol, 50, Resolution.Daily))
        else:
            self.averages[self.spy.Symbol].update(self.Time, self.spy.Price)

    def coarse_selection(self, coarse):
        self.update_spy()
        stocks = []
        coarse = [stock for stock in coarse if stock.Price > 10 and stock.Market == Market.USA and stock.HasFundamentalData]
        for stock in sorted(coarse, key=lambda x: x.DollarVolume, reverse=True)[:100]:
            symbol = stock.Symbol
            if symbol == self.spy.Symbol:
                continue
            if symbol not in self.averages:
                self.averages[symbol] = SelectionData(self.History(symbol, 200, Resolution.Daily))
            else:
                days_outdated = self.averages[symbol].days_outdated(self.Time)
                if days_outdated:
                    self.averages[symbol].update_from_history(self.History(symbol, days_outdated - 1, Resolution.Daily))
                else:
                    self.averages[symbol].update(self.Time, stock.Price)
                    self.averages[symbol].vol_ma.Update(self.Time, stock.Volume)
            # Rule #1: Trend template
            if not (stock.Price > self.averages[symbol].ma.Current.Value >
                    self.averages[symbol].ma_long.Current.Value > self.averages[symbol].ma_200.Current.Value):
                continue
            # Rule #2: Close must be above most recent high
            if not (stock.Price > self.averages[symbol].high.Current.Value):
                continue
            # Rule #3: High must be 7 weeks old (base breakout)
            if not self.averages[symbol].high.PeriodsSinceMaximum >= 35:
                continue
            # Rule #4: Breakout must be on high volume
            if not (stock.Volume / self.averages[symbol].vol_ma.Current.Value) >= 1.5:
                continue
            stocks.append(stock)
        # Rule #5: Rank by the highest ROC
        symbols = [stock.Symbol for stock in sorted(stocks, key=lambda x: self.averages[x.Symbol].roc.Current.Value, reverse=True)]
        return symbols

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
        if self.spy_downtrending:
            for security in self.Portfolio.Securities.keys():
                self.Liquidate(self.Portfolio.Securities[security].Symbol)
            return
        for symbol in self.ActiveSecurities.Keys:
            if symbol == self.spy.Symbol:
                continue
            if self.ActiveSecurities[symbol].Invested:
                if self.Portfolio[symbol].UnrealizedProfitPercent >= 0.20 or \
                    self.Portfolio[symbol].UnrealizedProfitPercent <= self.STOP_LOSS_PC * -1 or \
                        self.ActiveSecurities[symbol].Close < self.averages[symbol].ma.Current.Value or \
                            self.position_outdated(symbol):
                    self.Liquidate(symbol)
                    if self.open_positions.get(symbol):
                        del self.open_positions[symbol]
            elif slice[symbol].Close > slice[symbol].Open:
                position_size, position_value = self.calculate_position(symbol)
                if position_size > 0 and self.Portfolio.GetMarginRemaining(symbol, OrderDirection.Buy) > position_value:
                    self.MarketOrder(symbol, position_size)
                    self.open_positions[symbol] = self.Time

    def calculate_position(self, symbol):
        risk = self.ActiveSecurities[symbol].Price * self.STOP_LOSS_PC
        if risk <= 0:
            return 0, 0
        size = int((self.Portfolio.TotalPortfolioValue * self.EQUITY_RISK_PC) / risk)
        return size, size * self.ActiveSecurities[symbol].Price


class SelectionData():
    def __init__(self, history):
        self.roc = RateOfChangePercent(50)
        self.ma = SimpleMovingAverage(50)
        self.ma_long = SimpleMovingAverage(150)
        self.ma_200 = SimpleMovingAverage(200)
        self.high = Maximum(200)
        self.vol_ma = SimpleMovingAverage(50)
        self.update_from_history(history)
        self.time = None

    def update(self, time, price):
        self.roc.Update(time, price)
        self.ma.Update(time, price)
        self.ma_long.Update(time, price)
        self.ma_200.Update(time, price)
        self.high.Update(time, price)
        self.time = time

    def update_from_history(self, history):
        for data in history.itertuples():
            self.update(data.Index[1], data.close)
            self.vol_ma.Update(data.Index[1], data.volume)

    def days_outdated(self, time):
        if not self.time:
            return
        days = (time - self.time).days
        if days > 1:
            return days


class SPYSelectionData():
    def __init__(self, history):
        self.ma = SimpleMovingAverage(50)

        for data in history.itertuples():
            self.ma.Update(data.Index[1], data.close)

    def update(self, time, price):
        self.ma.Update(time, price)
