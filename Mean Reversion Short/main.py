# region imports
from datetime import timedelta

from AlgorithmImports import *
# endregion
from dateutil.parser import parse


class MeanReversionShort(QCAlgorithm):

    def Initialize(self):
        self.SetBrokerageModel(BrokerageName.InteractiveBrokersBrokerage)
        self.SetStartDate(2012, 1, 1)
        self.SetEndDate(2022, 1, 1)
        self.SetCash(10000)
        self.UniverseSettings.Resolution = Resolution.Daily
        self.AddUniverse(self.coarse_selection, self.fine_selection)
        self.fine_averages = {}
        self._changes = None
        self.EQUITY_RISK_PC = 0.01

    def coarse_selection(self, coarse):
        stocks = []
        stock_rsi_map = {}
        count = 0
        coarse = [stock for stock in coarse if stock.DollarVolume > 5000000 and stock.Price > 10 and stock.Market == Market.USA and stock.HasFundamentalData]
        for stock in sorted(coarse, key=lambda x: x.DollarVolume, reverse=True):
            if count == 500:
                break
            symbol = stock.Symbol
            data = CoarseData(self.History(symbol, 3, Resolution.Daily))
            # Rule #3: Last two days up
            # Rule #4: 3 day RSI above 85
            if data.rsi.Current.Value >= 85 and data.two_days_uptrend:
                stocks.append(symbol)
                stock_rsi_map[symbol] = data.rsi.Current.Value
                count += 1
        # rank stocks by RSI
        return sorted(stocks, key=lambda symbol: stock_rsi_map[symbol], reverse=True)

    def fine_selection(self, fine):
        stocks = []
        for stock in sorted(fine, key=lambda x: x.MarketCap, reverse=True):
            symbol = stock.Symbol
            self.fine_averages[symbol] = FineSelectionData(self.History(symbol, 10, Resolution.Daily))
            # Rule #1: ADX of past 7 days above 50
            if not self.fine_averages[symbol].adx.Current.Value > 50:
                continue
            natr = self.fine_averages[symbol].atr.Current.Value / stock.Price
            # Rule #2: ATR % of past 10 days above 5%
            if not natr > 0.05:
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
            return (self.Time - parse(self.ObjectStore.Read(str(symbol)))).days >= 2
        return True

    def OnData(self, slice) -> None:
        for symbol in self.ActiveSecurities.Keys:
            if self.ActiveSecurities[symbol].Invested:
                if self.Portfolio[symbol].UnrealizedProfitPercent >= 0.04 or \
                    self.Portfolio[symbol].UnrealizedProfitPercent <= -0.2 or \
                        self.position_outdated(symbol):
                    self.Liquidate(symbol)
                    if self.ObjectStore.ContainsKey(str(symbol)):
                        self.ObjectStore.Delete(str(symbol))
            else:
                position_size, position_value = self.calculate_position(symbol)
                if self.Portfolio.GetMarginRemaining(symbol, OrderDirection.Sell) > position_value:
                    self.MarketOrder(symbol, -position_size)
                    self.ObjectStore.Save(str(symbol), str(self.Time))

    def calculate_position(self, symbol):
        position_size = round((self.Portfolio.TotalPortfolioValue * self.EQUITY_RISK_PC) / self.fine_averages[symbol].atr.Current.Value)
        return position_size, position_size * self.ActiveSecurities[symbol].Price


class CoarseData():
    def __init__(self, history):
        self.rsi = RelativeStrengthIndex(3)
        self.close = RollingWindow[float](3)

        for data in history.itertuples():
            self.rsi.Update(data.Index[1], data.close)
            self.close.Add(data.close)

    @property
    def two_days_uptrend(self):
        try:
            return self.close[0] > self.close[1] > self.close[2]
        except:
            return False


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
