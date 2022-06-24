# region imports
from AlgorithmImports import *
# endregion
from dateutil.parser import parse


class MeanReversionMaLong(QCAlgorithm):
    def Initialize(self):
        self.SetBrokerageModel(BrokerageName.InteractiveBrokersBrokerage)
        self.SetStartDate(2012, 1, 1)
        self.SetEndDate(2022, 1, 1)
        self.SetCash(10000)
        self.UniverseSettings.Resolution = Resolution.Daily
        self.AddUniverse(self.coarse_selection)
        self.symbol_data = {}

    def coarse_selection(self, coarse):
        stocks = []
        coarse = sorted(
            [stock for stock in coarse if
             stock.DollarVolume > 2500000 and stock.Price > 1 and stock.Market == Market.USA and stock.HasFundamentalData],
            key=lambda x: x.DollarVolume, reverse=True
        )[:500]
        for stock in coarse:
            symbol = stock.Symbol
            if symbol not in self.symbol_data:
                self.symbol_data[symbol] = SymbolData(self.History(stock.Symbol, 200, Resolution.Daily))
            else:
                self.symbol_data[symbol].update(self.Time, stock.Price)
            # Rule #1: Trend template
            if not (stock.Price > self.symbol_data[symbol].ma.Current.Value >
                    self.symbol_data[symbol].ma_long.Current.Value > self.symbol_data[symbol].ma_200.Current.Value):
                continue
            ema = self.symbol_data[symbol].ema.Current.Value
            # Rule #2: 21 EMA must be above the 50 day
            if not ema > self.symbol_data[symbol].ma.Current.Value:
                continue
            # Rule #3: 7 EMA must be increasing
            if not self.symbol_data[symbol].strong_short_term_trend:
                continue
            # Rule #4: Price at or within 2% below EMA.
            if not ema >= stock.Price >= ema * 0.98:
                continue
            stocks.append(stock)
        symbols = [stock.Symbol for stock in sorted(stocks, key=lambda x: self.symbol_data[x.Symbol].roc.Current.Value)]
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
                if self.Portfolio[symbol].UnrealizedProfitPercent >= 0.3 or \
                        self.Portfolio[symbol].UnrealizedProfitPercent <= -0.05 or \
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
        self.ema = ExponentialMovingAverage(21)
        self.ema_short = ExponentialMovingAverage(7)
        self.ema_short_window = RollingWindow[float](3)
        self.ma = SimpleMovingAverage(50)
        self.ma_long = SimpleMovingAverage(150)
        self.ma_200 = SimpleMovingAverage(200)
        self.roc = RateOfChange(300)

        for data in history.itertuples():
            self.update(data.Index[1], data.close)

    def update(self, time, price):
        self.ema.Update(time, price)
        self.ema_short.Update(time, price)
        self.ema_short_window.Add(self.ema_short.Current.Value)
        self.ma.Update(time, price)
        self.ma_long.Update(time, price)
        self.ma_200.Update(time, price)
        self.roc.Update(time, price)

    @property
    def strong_short_term_trend(self):
        return self.ema_short.Current.Value > self.ema_short_window[2]
