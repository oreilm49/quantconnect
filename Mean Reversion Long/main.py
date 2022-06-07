# region imports
from datetime import timedelta

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
        self.AddUniverse(self.coarse_selection, self.fine_selection)
        self.coarse_averages = {}
        self.fine_averages = {}
        self._changes = None
        self.EQUITY_RISK_PC = 0.01

    def coarse_selection(self, coarse):
        stocks = []
        count = 0
        coarse = [stock for stock in coarse if stock.DollarVolume > 2500000 and stock.Price > 1 and stock.Market == Market.USA and stock.HasFundamentalData]
        for stock in sorted(coarse, key=lambda x: x.DollarVolume, reverse=True):
            if count == 500:
                break
            symbol = stock.Symbol
            if symbol not in self.coarse_averages or self.coarse_averages[symbol].is_outdated(self.Time):
                self.coarse_averages[symbol] = CoarseSelectionData(self.History(symbol, 50, Resolution.Daily))
            else:
                self.coarse_averages[symbol].update(self.Time, stock)
            if self.coarse_averages[symbol].rsi.Current.Value <= 30 and stock.Price > self.coarse_averages[symbol].ma.Current.Value:
                stocks.append(symbol)
                count += 1
        return stocks

    def fine_selection(self, fine):
        stocks = []
        for stock in sorted(fine, key=lambda x: x.MarketCap, reverse=True):
            symbol = stock.Symbol
            if symbol not in self.fine_averages or self.fine_averages[symbol].is_outdated(self.Time):
                self.fine_averages[symbol] = FineSelectionData(self.History(symbol, 10, Resolution.Daily))
            else:
                self.fine_averages[symbol].update(self.Time, stock)
            if not self.fine_averages[symbol].adx.Current.Value >= 45:
                continue
            natr = self.fine_averages[symbol].atr.Current.Value / stock.Price
            # Rule #3: ATR% above 4
            if natr < 0.04:
                continue
            stocks.append(symbol)
            if len(stocks) == 10:
                break
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
                position_size, position_value = self.calculate_position(symbol)
                if self.Portfolio.GetMarginRemaining(symbol, OrderDirection.Buy) > position_value:
                    self.MarketOrder(symbol, position_size)
                    self.ObjectStore.Save(str(symbol), str(self.Time))

    def calculate_position(self, symbol):
        position_size = round((self.Portfolio.TotalPortfolioValue * self.EQUITY_RISK_PC) / self.fine_averages[symbol].atr.Current.Value)
        return position_size, position_size * self.ActiveSecurities[symbol].Price


class CoarseSelectionData():
    def __init__(self, history):
        self.rsi = RelativeStrengthIndex(3)
        self.ma = SimpleMovingAverage(50)

        for data in history.itertuples():
            self.rsi.Update(data.Index[1], data.close)
            self.ma.Update(data.Index[1], data.close)

    def update(self, time, stock):
        self.rsi.Update(time, stock.Price)
        self.ma.Update(time, stock.Price)

    def is_outdated(self, time):
        return (time - self.ma.Current.Time).days > 1 or (time - self.rsi.Current.Time).days > 1


class FineSelectionData():
    def __init__(self, history):
        self.adx = AverageDirectionalIndex(7)
        self.atr = AverageTrueRange(10)

        for data in history.itertuples():
            self.update(data)

    def update(self, data):
        trade_bar = TradeBar(data.Index[1], data.Index[0], data.open, data.high, data.low, data.close, data.volume, timedelta(1))
        self.adx.Update(trade_bar)
        self.atr.Update(trade_bar)

    def is_outdated(self, time):
        return (time - self.adx.Current.Time).days > 1 or (time - self.atr.Current.Time).days > 1
