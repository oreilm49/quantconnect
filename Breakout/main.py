from AlgorithmImports import QCAlgorithm, Resolution, BrokerageName

from constants import HVC, SHORT, INSIDE_DAY, KMA_PULLBACK, POCKET_PIVOT, BREAKOUT, BACKTEST_SYMBOLS
from indicators import SymbolIndicators


class Breakout(QCAlgorithm):
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
            self.screened_symbols = BACKTEST_SYMBOLS
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
            if self.hvc(symbol):
                self.buy(symbol, order_tag=HVC)
            if self.inside_day(symbol):
                self.buy(symbol, order_tag=INSIDE_DAY)
            if self.kma_pullback(symbol):
                self.buy(symbol, order_tag=KMA_PULLBACK)
            if self.pocket_pivot(symbol):
                self.buy(symbol, order_tag=POCKET_PIVOT)
            breakout = self.breakout(symbol)
            if breakout:
                self.buy(symbol, order_tag=f"{BREAKOUT}: {breakout}")
        # Shorting logic
        for symbol, indicators in self.symbol_map.items():
            if not self.ActiveSecurities[symbol].Invested:
                continue
            if indicators.uptrending:
                continue
            if self.short_entry(symbol):
                self.short(symbol)


    
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
    
    def short(self, symbol):
        position_size = self.get_position_size(symbol)
        position_value = position_size * self.ActiveSecurities[symbol].Price
        if position_value < self.Portfolio.Cash:
                self.MarketOrder(symbol, position_size * -1, tag=SHORT)
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
    
    def hvc(self, symbol): 
        """ 
        This pattern occurs after a stock gaps up on huge volume due to earnings or another major news event. 
        The most important point for the stock going forwards is the gap up closing price. 
        Highest Volume Ever (HVE) 
        · Highest Volume in 1 Year (HVIPO) 
        · Highest Volume Since IPO Week (HVIPO) 
        · Higheset Volume Since Last EPS (HVLE) 
        These characteristics show clear INSTITUTIONAL DEMAND. 
        · 75% (or more) closing range on gap day 
        · Gap to new highs or within 20% of prior highs         
        The closing price of the gap up on day 1 is the High Volume Close (HVC). 
        Exit: 3-5% hard stop below the HVC OR an end-of-day close below this level depending on the market environment. 
        Note: 
        - removed gap up logic 
        """ 
        indicators: SymbolIndicators = self.symbol_map[symbol] 
        trade_bar_lts = indicators.trade_bar_window[0] 
        trade_bar_prev = indicators.trade_bar_window[1] 
        # highest vol in 200 days 
        if not indicators.max_volume.Current.Value == trade_bar_lts.Volume: 
            return False 
        # closing range PC above 75; formula = ((close - low) / ((high - low) / 100)) 
        if not indicators.close_range_pc >= 75: 
            return False
        
        if trade_bar_lts.Open < trade_bar_prev.Close and trade_bar_lts.Close < trade_bar_prev.Close:
            return False
        return True
    
    def inside_day(self, symbol): 
        """ 
        · Inside Day (today's whole price bar within yesterday's)
        Two day chart pattern.
        The body of the second candle must fit inside the first candle.
        Vol on the second day must be below average.
        Second day must have a positive close.
        Must occur within a general market uptrend.
        Entry:
            Price closes above the high of the first day after the pattern.
        """ 
        indicators: SymbolIndicators = self.symbol_map[symbol] 
        trade_bar_lts = indicators.trade_bar_window[0] 
        pattern_day_2 = indicators.trade_bar_window[1] 
        pattern_day_1 = indicators.trade_bar_window[2] 
        # inside day 
        if not ((pattern_day_2.High < pattern_day_1.High) and (pattern_day_2.Low > pattern_day_1.Low)): 
            return False 
        # below avg vol 
        if pattern_day_2.Volume > indicators.sma_volume.Current.Value: 
            return False 
        # ensure positive close 
        if pattern_day_2.Open > pattern_day_2.Close: 
            return False 
        # must occur within a base 
        if not indicators.high_7_weeks_ago: 
            return False 
        # must occur within an uptrend 
        if not indicators.uptrending : 
            return False
        # closed above the inside day high
        return trade_bar_lts.Close > pattern_day_1.High
    
    def kma_pullback(self, symbol):
        """
        The point of this setup is to capture weakness in leading stocks as they find support from institutions on the 10-week moving average.
        Here are some key things to look for:
        · Stock should be pulling back from new highs (52-week or all-time)
        · Uptrending 10-week Moving Average
        · Volume should be low on a pullback
        · Buy occurs after stock reverses higher
        """
        indicators: SymbolIndicators = self.symbol_map[symbol]
        trade_bar_lts = indicators.trade_bar_window[0]
        trade_bar_prev = indicators.trade_bar_window[1]
        # recent new high (within the three weeks)
        if indicators.high_3_weeks_ago:
            return False
        # touched the 50 day
        if not (trade_bar_prev.Low <= indicators.sma_window[1]):
            return False
        # up day
        if trade_bar_lts.Open > trade_bar_lts.Close:
            return False
        # low above 50 day
        if indicators.sma_window[0] >= trade_bar_lts.Low:
            return False
        return True
    
    def pocket_pivot(self, symbol):
        """
        A Pocket Pivot is the current up day's volume must be larger than any of the down volume days in the prior 10 days.
        """
        indicators: SymbolIndicators = self.symbol_map[symbol]
        trade_bar_lts = indicators.trade_bar_window[0]
        # up day
        if indicators.trade_bar_window[0].Open > indicators.trade_bar_window[0].Close:
            return False
        # pocket pivot
        if indicators.max_vol_on_down_day > indicators.trade_bar_window[0].Volume:
            return False
        # low of the day is greater than SMA
        if trade_bar_lts.Low > indicators.sma.Current.Value[0]:
            return False
        # must occur within a base
        if not indicators.high_7_weeks_ago:
            return False
        return True
    
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

    def short_entry(self, symbol) -> bool:
        """
        A stock has had a powerful run up and topped.
        After topping it begins a downtrend, eventually violating the 50 MA.
        In pullbacks it reclaims the 50 day.
        A 3rd violation on heavy volume signals a short entry.
        Entry criteria (not implemented yet):
        * 50 MA below 200 MA
        * Price violates 50 MA x 3
        * 3rd violation is on heavy volume (100% over vol 50 ma)
        * Prior rally was strong
        """
        indicators: SymbolIndicators = self.symbol_map[symbol]
        return (indicators.sma.Current.Value < indicators.sma_200.Current.Value) and indicators.sma_violated()
    
    def update_screened_symbols(self):
        self.screened_symbols = self.Download(self.SYMBOLS_URL).split("\r\n")
        self.live_log(f"symbols updated: {','.join(self.screened_symbols)}")
        for symbol in list(self.symbol_map.keys()):
            if symbol.Value not in self.screened_symbols:
                self.live_log(f"removed from indicators: {symbol.Value}")
                del self.symbol_map[symbol]
