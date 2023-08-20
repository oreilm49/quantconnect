# region imports
from AlgorithmImports import *
# endregion
from constants import SIGNAL_BUY, SIGNAL_SELL, LONG_LOOKBACK
from indicators import MarketIndexData, SymbolIndicators


class FTDRotation(QCAlgorithm):
    def Initialize(self):
        self.SetStartDate(2018, 1, 1)
        self.SetCash(100000)
        self.spy = self.AddEquity('SPY', Resolution.Daily)
        self.qqq = self.AddEquity('QQQ', Resolution.Daily)
        self.market_data = {}
        self.symbol_data = {}

    def coarse_selection(self, coarse):
        stocks = {self.spy.Symbol, self.qqq.Symbol}
        for stock in sorted(coarse, key=lambda x: x.DollarVolume, reverse=True)[:100]:
            if stock.Price < 10:
                continue
            stocks.add(stock.Symbol)
        for stock in list(self.market_data.Keys()):
            if stock not in stocks:
                del self.market_data[stock]
        return list(stocks)
    
    def fine_selection(self, fine):
        stocks = {self.spy.Symbol, self.qqq.Symbol}
        for stock in fine:
            if stock.AssetClassification.MorningstarIndustryGroupCode != 311:
                continue
            stocks.add(stock.Symbol)
        return list(stocks)

    def update_market_data(self, trade_bar):
        if trade_bar.Symbol in (self.spy.Symbol, self.qqq.Symbol):
            if trade_bar.Symbol not in self.market_data:
                self.market_data[trade_bar.Symbol] = MarketIndexData(self.History(trade_bar.Symbol, 30, Resolution.Daily))
            else:
                self.market_data.update(trade_bar)

    def market_signal(self) -> str:
        spy = self.market_data[self.spy.Symbol]
        qqq = self.market_data[self.qqq.Symbol]
        if spy.signal == qqq.signal == SIGNAL_BUY:
            return SIGNAL_BUY
        if spy.signal == qqq.signal == SIGNAL_SELL:
            return SIGNAL_SELL

    def OnData(self, data):
        for symbol in self.ActiveSecurities.Keys:
            if not data.Bars.ContainsKey(symbol):
                continue
            if symbol.Value in ('SPY', 'QQQ'):
                self.update_market_data(data.Bars[symbol])
                continue        
            if symbol not in self.symbol_data:
                self.symbol_data[symbol] = SymbolIndicators(self.History(symbol, 50, Resolution.Daily))
            else:
                self.symbol_data[symbol].update(data.Bars[symbol])
        if self.market_signal == SIGNAL_BUY:
            

        
