# region imports
from AlgorithmImports import *
# endregion
from dateutil.parser import parse

NUM_OF_SYMBOLS = "number_of_symbols"


class MeanReversionBBLong(QCAlgorithm):
    def Initialize(self):
        self.SetBrokerageModel(BrokerageName.InteractiveBrokersBrokerage)
        self.SetStartDate(1995, 1, 1)
        self.SetEndDate(2022, 1, 1)
        self.SetCash(10000)
        self.UniverseSettings.Resolution = Resolution.Daily
        self.AddUniverse(self.coarse_selection)
        self.symbol_data = {}

    def coarse_selection(self, coarse):
        stocks = []
        coarse = sorted(
            [stock for stock in coarse if stock.DollarVolume > 2500000 and stock.Price > 1 and stock.Market == Market.USA and stock.HasFundamentalData],
            key=lambda x: x.DollarVolume, reverse=True
        )[:500]
        for stock in coarse:
            symbol = stock.Symbol
            if symbol not in self.symbol_data:
                self.symbol_data[symbol] = SymbolData(self.History(stock.Symbol, 150, Resolution.Daily))
            else:
                self.symbol_data[symbol].update(self.Time, stock.Price)
            # Rule #1: Stock must be in long term uptrend (above 50 day)
            # Rule #2: 3 day RSI is below 30
            if not (self.symbol_data[symbol].rsi.Current.Value < 30 and stock.Price > self.symbol_data[symbol].ma.Current.Value >
                    self.symbol_data[symbol].ma_long.Current.Value):
                continue
            # Rule #3: Stock must be at or below the lower bollinger band
            if not stock.Price <= self.symbol_data[symbol].bb.LowerBand.Current.Value:
                continue
            stocks.append(stock)
        # Rule #4: Rank by the lowest RSI = most oversold stocks
        symbols = [stock.Symbol for stock in sorted(stocks, key=lambda x: self.symbol_data[x.Symbol].rsi.Current.Value)]
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
                    self.Portfolio[symbol].UnrealizedProfitPercent <= -0.2 or \
                        self.position_outdated(symbol):
                    self.Liquidate(symbol)
                    if self.ObjectStore.ContainsKey(str(symbol)):
                        self.ObjectStore.Delete(str(symbol))
            else:
                if self.ActiveSecurities[symbol].Price == 0:
                    continue
                position_size, position_value = self.calculate_position(symbol)
                if self.Portfolio.GetMarginRemaining(symbol, OrderDirection.Buy) > position_value:
                    self.MarketOrder(symbol, position_size)
                    self.ObjectStore.Save(str(symbol), str(self.Time))

    def calculate_position(self, symbol):
        position_value = self.Portfolio.TotalPortfolioValue / 10
        return round(position_value / self.ActiveSecurities[symbol].Price), position_value


class SymbolData:
    def __init__(self, history):
        self.rsi = RelativeStrengthIndex(3)
        self.ma = SimpleMovingAverage(50)
        self.ma_long = SimpleMovingAverage(150)
        self.bb = BollingerBands(21, 2)

        for data in history.itertuples():
            self.update(data.Index[1], data.close)

    def update(self, time, price):
        self.rsi.Update(time, price)
        self.ma.Update(time, price)
        self.ma_long.Update(time, price)
        self.bb.Update(time, price)
