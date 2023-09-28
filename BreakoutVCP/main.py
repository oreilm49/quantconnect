from AlgorithmImports import QCAlgorithm, Resolution, BrokerageName, OrderProperties, TimeInForce
from datetime import timedelta, datetime
from indicators import SymbolIndicators


HVC = 'high volume close'
INSIDE_DAY = 'inside day'
KMA_PULLBACK = 'key moving average pullback'
POCKET_PIVOT = 'pocket pivot'
BREAKOUT = 'breakout'


class BreakoutVCP(QCAlgorithm):
    def Initialize(self):
        self.SetCash(10000)
        self.UniverseSettings.Resolution = Resolution.Daily
        self.SetBrokerageModel(BrokerageName.InteractiveBrokersBrokerage)
        self.EQUITY_RISK_PC = 0.0075
        self.AddUniverse(self.coarse_selection)
        self.symbol_map = {}
        self.AddEquity("SPY", Resolution.Daily)
        self.SL_RISK_PC = -0.05
        self.TP_TARGET = 0.20
        self.SYMBOLS_URL = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vRajMcf0SW61y_kCO9s1mhvCxGlGq9PgSRyQyNyQCx9ALfOF800f22Z0OKkL_-PU_jBWowdOBkM6FtM/pub?gid=0&single=true&output=csv'
        self.screened_symbols = []
        if not self.LiveMode:
            # backtest configuration
            self.screened_symbols = ["ASAN", "TSLA", "RBLX", "DOCN", "FTNT", "DDOG", "NET", "BILL", "NVDA", "AMBA", "INMD", "AMEH", "AEHR", "SITM", "CROX"]
            self.SetStartDate(2021, 1, 1)
            self.SetEndDate(2021, 12, 31)
            

    def live_log(self, msg):
        if self.LiveMode:
            self.Log(msg)
        else:
            self.Debug(msg)

    def coarse_selection(self, coarse):
        if self.LiveMode:
            self.update_screened_symbols()
        return [stock.Symbol for stock in coarse if stock.Symbol.Value in self.screened_symbols]

    def OnData(self, data):
        symbols = []
        for symbol in self.ActiveSecurities.Keys:
            if symbol.Value not in self.screened_symbols:
                continue
            if not data.Bars.ContainsKey(symbol):
                continue
            if symbol not in self.symbol_map:
                self.symbol_map[symbol] = SymbolIndicators(self, symbol)
            else:
                self.symbol_map[symbol].update(data.Bars[symbol])
            if not self.symbol_map[symbol].ready:
                continue
            if self.sell_signal(symbol, data):
                self.Liquidate(symbol)
            if self.symbol_map[symbol].uptrending and not self.ActiveSecurities[symbol].Invested:
                symbols.append(symbol)
        self.live_log("processing on data")
        if not symbols:
            self.live_log("no symbols")
        # sort stocks by lowest volatility
        for symbol in sorted(symbols, key=lambda symbol: self.symbol_map[symbol].atrp(data.Bars[symbol].Close)):
            breakout = self.breakout(symbol)
            if breakout:
                self.buy(symbol, order_tag=f"{BREAKOUT}: {breakout}")
    
    def buy(self, symbol, order_tag=None, order_properties=None, price=None):
        position_size = self.get_position_size(symbol)
        position_value = position_size * self.ActiveSecurities[symbol].Price
        if position_value < self.Portfolio.Cash:
            if price:
                self.live_log(f"Limit order {symbol.Value} {position_value}: {order_tag or 'no tag'}: {str(price)}")
                self.StopMarketOrder(symbol, position_size, price, order_tag, order_properties)
            else:
                self.live_log(f"Market order {symbol.Value} {position_value}: {order_tag or 'no tag'}")
                self.MarketOrder(symbol, position_size, tag=order_tag)
        else:
            self.live_log(f"insufficient cash ({self.Portfolio.Cash}) to purchase {symbol.Value}")

    def get_position_size(self, symbol):
        """
        Gets the lowest risk position size
        volatility_size = ($total equity * portfolio risk %) / ATR(21)
        risk_size = ($total equity * portfolio risk %) / $value of risk on trade
        """
        volatility_size = (self.Portfolio.TotalPortfolioValue * self.EQUITY_RISK_PC) / self.symbol_map[symbol].atr.Current.Value
        risk_size = (self.Portfolio.TotalPortfolioValue * self.EQUITY_RISK_PC) / (self.ActiveSecurities[symbol].Price * (self.SL_RISK_PC * -1))
        return round(min(volatility_size, risk_size))
    
    def sell_signal(self, symbol, slice):
        profit = self.Portfolio[symbol].UnrealizedProfitPercent
        return profit >= self.TP_TARGET or profit <= self.SL_RISK_PC
    
    def breakout(self, symbol):
        """
        Identifies if the stock is uptrending and is within 5% of a breakout level.
        Price must be above the breakout level.
        The breakout level must be within 10% of the 50 day high.

        :return: The breakout level or None.
        """
        indicators: SymbolIndicators = self.symbol_map[symbol]
        trade_bar_lts = indicators.trade_bar_window[0]
        if not (indicators.uptrending and indicators.breakout_window.IsReady):
            return
        level = indicators.breakout_window[0]
        if not (level * 1.05 > trade_bar_lts.Close > level):
            return
        if indicators.max_price.Current.Value > level * 1.1:
            return
        return level
    
    def update_screened_symbols(self):
        self.screened_symbols = self.Download(self.SYMBOLS_URL).split("\r\n")
        self.live_log(f"symbols updated: {','.join(self.screened_symbols)}")
        for symbol in list(self.symbol_map.keys()):
            if symbol.Value not in self.screened_symbols:
                self.live_log(f"removed from indicators: {symbol.Value}")
                del self.symbol_map[symbol]
