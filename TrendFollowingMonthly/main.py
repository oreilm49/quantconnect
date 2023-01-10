from AlgorithmImports import *


class MyQC500(QC500UniverseSelectionModel):
    """
    Optimized to select the top 250 stocks by dollar volume
    """
    numberOfSymbolsCoarse = 250


class TrendFollowingMonthly(QCAlgorithm):
    def Initialize(self):
        self.UniverseSettings.Resolution = Resolution.Daily
        self.SetStartDate(2020, 1, 1)
        self.SetCash(100000)
        self.SetWarmUp(timedelta(200), Resolution.Daily)
        self.UniverseSettings.Resolution = Resolution.Daily
        self.SetBrokerageModel(BrokerageName.InteractiveBrokersBrokerage)
        # self.AddUniverseSelection(MyQC500()) # it might be this
        self.SetUniverseSelection(MyQC500())
        self.symbols = {}
        self.EQUITY_RISK_PC = 0.01
        self.spy = self.AddEquity("SPY", Resolution.Daily)
        self.last_month = -1

    @property
    def spy_downtrending(self) -> bool:
        spy_data = SPYSymbolData(self.History(self.spy.Symbol, 200, Resolution.Daily))
        return spy_data.ma.Current.Value > self.spy.Price

    def OnData(self, data):
        if self.Time.month == self.last_month:
            return
        self.last_month = self.Time.month
        self.Debug(str(self.Time))
        if self.spy_downtrending:
            for security in self.Portfolio.Securities.keys():
                self.Liquidate(self.Portfolio.Securities[security].Symbol)
            return   
        securities = [symbol for symbol in self.ActiveSecurities.Keys if symbol in data.Bars]
        for symbol in securities:
            self.symbols[symbol] = SymbolData(self.History(symbol, 200, Resolution.Daily))
        securities = [symbol for symbol in securities if self.symbols[symbol].atrp(data.Bars[symbol].Close) <= 5]
        top_performers = sorted(
            securities, 
            key=lambda symbol: self.symbols[symbol].roc.Current.Value, 
            reverse=True,
        )[:10]
        for symbol in securities:
            if self.ActiveSecurities[symbol].Invested and symbol not in top_performers:
                self.Liquidate(symbol)
        for symbol in top_performers:
            if not self.ActiveSecurities[symbol].Invested:
                self.buy(symbol)
    
    def buy(self, symbol):
        position_size = round((self.Portfolio.TotalPortfolioValue * self.EQUITY_RISK_PC) / self.symbols[symbol].atr.Current.Value)
        position_value = position_size * self.ActiveSecurities[symbol].Price
        if position_value < self.Portfolio.Cash:
            self.MarketOrder(symbol, position_size)


class SymbolData:
    def __init__(self, history):
        self.roc = RateOfChangePercent(200)
        self.atr = AverageTrueRange(21)

        for data in history.itertuples():
            self.update(
                TradeBar(data.Index[1], data.Index[0], data.open, data.high, data.low, data.close, data.volume, timedelta(1))
            )

    def update(self, trade_bar):
        self.atr.Update(trade_bar)
        self.roc.Update(trade_bar.EndTime, trade_bar.Close)

    def atrp(self, close):
        return (self.atr.Current.Value / close) * 100
    

class SPYSymbolData():
    def __init__(self, history):
        self.ma = SimpleMovingAverage(200)

        for data in history.itertuples():
            self.ma.Update(data.Index[1], data.close)

    def update(self, time, price):
        self.ma.Update(time, price)