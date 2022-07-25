#region imports
from datetime import timedelta

from AlgorithmImports import *
#endregion


class NewHighBreakoutIBD50(QCAlgorithm):

    def Initialize(self):
        self.SetBrokerageModel(BrokerageName.InteractiveBrokersBrokerage)
        self.SetStartDate(2022, 4, 1)
        self.SetEndDate(2022, 7, 1)
        self.SetCash(10000)
        self.UniverseSettings.Resolution = Resolution.Daily
        self.spy = self.AddEquity("SPY", Resolution.Daily)
        self.SetBenchmark("SPY")
        self.AddUniverse(self.coarse_selection)
        self.averages = {}
        self._changes = None
        self.EQUITY_RISK_PC = 0.01
        self.open_positions = {}
        self.holdings_symbols = []
    
    def update_holdings_symbols(self):
        dataframe = pd.read_csv('https://www.innovatoretfs.com/etf/xt_holdings.csv')
        if not dataframe.empty:
            dataframe = dataframe[(dataframe['Account'] == 'FFTY')]
            self.holdings_symbols = dataframe.StockTicker.values
        self.holdings_symbols = []

    def update_spy(self):
        if self.spy.Symbol not in self.averages:
            self.averages[self.spy.Symbol] = SPYSelectionData(self.History(self.spy.Symbol, 200, Resolution.Daily))
        else:
            self.averages[self.spy.Symbol].update(self.Time, self.spy.Price)
    
    @property
    def is_monday(self):
        return self.Time.weekday() == 0

    def coarse_selection(self, coarse):
        self.update_spy()
        if self.is_monday or not self.holdings_symbols:
            self.update_holdings_symbols()
        stocks = []
        for stock in coarse:
            symbol = stock.Symbol
            if symbol == self.spy.Symbol or symbol not in self.holdings_symbols:
                continue
            if symbol not in self.averages:
                self.averages[symbol] = SelectionData(self.History(symbol, 100, Resolution.Daily))
            self.averages[symbol].update(self.Time, stock.Price)
            if not (stock.Price > self.averages[symbol].ma.Current.Value):
                continue
            if not self.averages[symbol].roc.Current.Value > 0:
                continue
            stocks.append(symbol)
        return sorted(stocks, key=lambda x: self.averages[x].roc.Current.Value, reverse=True)

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
                    self.Portfolio[symbol].UnrealizedProfitPercent <= -0.08 or \
                        self.ActiveSecurities[symbol].Close < self.averages[symbol].ma.Current.Value or \
                            self.position_outdated(symbol):
                    self.Liquidate(symbol)
            else:
                high = Maximum(100)
                atr = AverageTrueRange(21)
                for data in self.History(symbol, 100, Resolution.Daily).itertuples():
                    if self.Time != data.Index[1]:
                        high.Update(data.Index[1], data.high)
                    atr.Update(
                        TradeBar(data.Index[1], data.Index[0], data.open, data.high, data.low, data.close, data.volume, timedelta(1))
                    )
                if high.Current.Value * 1.05 > self.ActiveSecurities[symbol].Close >= high.Current.Value:
                    if high.PeriodsSinceMaximum >= 25:
                        position_size = self.calculate_position_size(atr.Current.Value)
                        position_value = position_size * self.ActiveSecurities[symbol].Price
                        if position_value < self.Portfolio.Cash:
                            self.MarketOrder(symbol, position_size)
                            self.open_positions[symbol] = self.Time

    def calculate_position_size(self, atr):
        return round((self.Portfolio.TotalPortfolioValue * self.EQUITY_RISK_PC) / atr)


class SelectionData():
    def __init__(self, history):
        self.ma = SimpleMovingAverage(50)
        self.roc = RateOfChangePercent(100)

        for data in history.itertuples():
            self.update(data.Index[1], data.close)

    def update(self, time, price):
        self.ma.Update(time, price)
        self.roc.Update(time, price)


class SPYSelectionData():
    def __init__(self, history):
        self.ma = SimpleMovingAverage(200)

        for data in history.itertuples():
            self.ma.Update(data.Index[1], data.close)

    def update(self, time, price):
        self.ma.Update(time, price)
