# region imports
from datetime import timedelta

from AlgorithmImports import *
# endregion
from dateutil.parser import parse


class MeanReversionLong(QCAlgorithm):

    def Initialize(self):
        self.SetBrokerageModel(BrokerageName.InteractiveBrokersBrokerage)
        self.SetStartDate(2018, 1, 1)
        self.SetEndDate(2019, 1, 1)
        self.SetCash(10000)
        self.UniverseSettings.Resolution = Resolution.Daily
        self.AddUniverse(self.coarse_selection)
        self.averages = {}
        self._changes = None
        self.EQUITY_RISK_PC = 0.01

    def coarse_selection(self, coarse):
        stocks = []
        for stock in [stock for stock in coarse if stock.DollarVolume > 2500000 and stock.Price > 1 and stock.Market == Market.USA and stock.HasFundamentalData]:
            symbol = stock.Symbol
            if symbol not in self.averages:
                self.averages[symbol] = SelectionData(self.History(symbol, 150, Resolution.Daily))
            self.averages[symbol].update(self.Time, stock)
            if self.averages[symbol].is_ready() and stock.Price > self.averages[symbol].ma.Current.Value and \
                self.averages[symbol].rsi.Current.Value <= 30:
                stocks.append(symbol)
        for symbol in set(self.averages.keys()):
            if symbol not in stocks:
                del self.averages[symbol]
        return stocks

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
                    self.Portfolio[symbol].UnrealizedProfitPercent <= -0.2 or \
                        self.position_outdated(symbol):
                    self.Liquidate(symbol)
                    if self.ObjectStore.ContainsKey(str(symbol)):
                        self.ObjectStore.Delete(str(symbol))
            else:
                adx = AverageDirectionalIndex(7)
                atr = AverageTrueRange(10)
                for data in self.History(symbol, 100, Resolution.Daily).itertuples():
                    trade_bar = TradeBar(data.Index[1], data.Index[0], data.open, data.high, data.low, data.close, data.volume, timedelta(1))
                    atr.Update(trade_bar)
                    adx.Update(trade_bar)
                if not adx.Current.Value >= 45:
                    continue
                natr = 100 * (atr.Current.Value / self.ActiveSecurities[symbol].Price)
                if natr < 0.04:
                    continue
                position_size = self.calculate_position_size(atr.Current.Value)
                position_value = position_size * self.ActiveSecurities[symbol].Price
                if position_value < self.Portfolio.Cash:
                    self.MarketOrder(symbol, position_size)
                    self.ObjectStore.Save(str(symbol), str(self.Time))

    def calculate_position_size(self, atr):
        return round((self.Portfolio.TotalPortfolioValue * self.EQUITY_RISK_PC) / atr)


class SelectionData():
    def __init__(self, history):
        self.ma = SimpleMovingAverage(150)
        self.rsi = RelativeStrengthIndex(3)

        for data in history.itertuples():
            self.ma.Update(data.Index[1], data.close)
            self.rsi.Update(data.Index[1], data.close)

    def is_ready(self):
        return self.ma.IsReady and self.rsi.IsReady

    def update(self, time, stock):
        self.ma.Update(time, stock.Price)
        self.rsi.Update(time, stock.Price)
