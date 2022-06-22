# region imports
from datetime import timedelta

from AlgorithmImports import *
# endregion
from dateutil.parser import parse

NUM_OF_SYMBOLS = "number_of_symbols"


class MeanReversionLong(QCAlgorithm):
    def Initialize(self):
        self.SetBrokerageModel(BrokerageName.InteractiveBrokersBrokerage)
        self.SetStartDate(2012, 1, 1)
        self.SetEndDate(2012, 2, 1)
        self.SetCash(10000)
        self.UniverseSettings.Resolution = Resolution.Daily
        self.AddUniverse(self.coarse_selection)
        self.coarse_averages = {}
        self.atrs = {}
        self._changes = None
        self.EQUITY_RISK_PC = 0.01

    def coarse_selection(self, coarse):
        stocks = []
        # clear atrs each time so we don't accidentally use outdated data.
        self.atrs = {}
        coarse = sorted(
            [stock for stock in coarse if stock.DollarVolume > 2500000 and stock.Price > 1 and stock.Market == Market.USA and stock.HasFundamentalData],
            key=lambda x: x.DollarVolume, reverse=True
        )[:500]
        price_data = self.History([stock.Symbol for stock in coarse], 50, Resolution.Daily)
        for stock in coarse:
            symbol = stock.Symbol
            self.coarse_averages[symbol] = CoarseSelectionData(price_data.loc[symbol])
            # Rule #1: Stock must be in long term uptrend (above 50 day)
            # Rule #4: 3 day RSI is below 30
            if not (self.coarse_averages[symbol].rsi.Current.Value < 30 and stock.Price > self.coarse_averages[symbol].ma.Current.Value):
                continue
            ohlc_data = OHLCData(price_data.loc[symbol], symbol)
            # Rule #2: 7 day ADX above 45 (strong short term trend)
            if not ohlc_data.adx.Current.Value > 45:
                continue
            natr = ohlc_data.atr.Current.Value / stock.Price
            # Rule #3: ATR% above 4
            if natr < 0.04:
                continue
            self.atrs[symbol] = ohlc_data.atr.Current.Value
            stocks.append(stock)
        # Rule #6: Rank by the lowest RSI = most oversold stocks
        symbols = [stock.Symbol for stock in sorted(stocks, key=lambda x: self.coarse_averages[x.Symbol].rsi.Current.Value)]
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
                    if self.ObjectStore.ContainsKey(NUM_OF_SYMBOLS):
                        self.ObjectStore.Save(NUM_OF_SYMBOLS, str(int(self.ObjectStore.Read(NUM_OF_SYMBOLS)) - 1))
            else:
                if self.ObjectStore.ContainsKey(NUM_OF_SYMBOLS) and int(self.ObjectStore.Read(NUM_OF_SYMBOLS)) >= 10:
                    continue
                if symbol not in self.atrs:
                    continue
                position_size, position_value = self.calculate_position(symbol, self.atrs[symbol])
                if self.Portfolio.GetMarginRemaining(symbol, OrderDirection.Buy) > position_value:
                    self.MarketOrder(symbol, position_size)
                    self.ObjectStore.Save(str(symbol), str(self.Time))
                    if self.ObjectStore.ContainsKey(NUM_OF_SYMBOLS):
                        self.ObjectStore.Save(NUM_OF_SYMBOLS, str(int(self.ObjectStore.Read(NUM_OF_SYMBOLS)) + 1))
                    else:
                        self.ObjectStore.Save(NUM_OF_SYMBOLS, "1")

    def calculate_position(self, symbol, atr):
        position_size = round((self.Portfolio.TotalPortfolioValue * self.EQUITY_RISK_PC) / atr)
        return position_size, position_size * self.ActiveSecurities[symbol].Price


class CoarseSelectionData():
    def __init__(self, history):
        self.rsi = RelativeStrengthIndex(3)
        self.ma = SimpleMovingAverage(50)

        for data in history.itertuples():
            self.rsi.Update(data.Index, data.close)
            self.ma.Update(data.Index, data.close)


class OHLCData():
    def __init__(self, history, symbol):
        self.adx = AverageDirectionalIndex(7)
        self.atr = AverageTrueRange(10)
        self.symbol = symbol

        for data in history.itertuples():
            self.update(data)

    def update(self, data, time=None):
        trade_bar = TradeBar(time or data.Index, self.symbol, data.open, data.high, data.low, data.close, data.volume, timedelta(1))
        self.adx.Update(trade_bar)
        self.atr.Update(trade_bar)
