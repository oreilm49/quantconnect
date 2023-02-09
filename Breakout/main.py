from AlgorithmImports import SimpleMovingAverage, AverageTrueRange, RollingWindow, TradeBar,\
    QCAlgorithm, Resolution, BrokerageName, QC500UniverseSelectionModel, Maximum, Market
from datetime import timedelta


HVC = 'high volume close'
INSIDE_DAY = 'inside day'
KMA_PULLBACK = 'key moving average pullback'
POCKET_PIVOT = 'pocket pivot'


class SymbolIndicators:
    def __init__(self, history) -> None:
        self.sma = SimpleMovingAverage(50)
        self.sma_volume = SimpleMovingAverage(50)
        self.sma_200 = SimpleMovingAverage(200)
        self.atr = AverageTrueRange(21)
        self.trade_bar_window = RollingWindow[TradeBar](10)
        self.max_volume = Maximum(200)
        self.max_price = Maximum(200)
        self.sma_window = RollingWindow[float](2)

        for data in history.itertuples():
            trade_bar = TradeBar(data.Index[1], data.Index[0], data.open, data.high, data.low, data.close, data.volume, timedelta(1))
            self.update(trade_bar)
        
    def update(self, trade_bar):
        self.sma.Update(trade_bar.EndTime, trade_bar.Close)
        self.sma_volume.Update(trade_bar.EndTime, trade_bar.Volume)
        self.sma_200.Update(trade_bar.EndTime, trade_bar.Close)
        self.atr.Update(trade_bar)
        self.trade_bar_window.Add(trade_bar)
        self.max_volume.Update(trade_bar.EndTime, trade_bar.Volume)
        self.max_price.Update(trade_bar.EndTime, trade_bar.High)
        self.sma_window.Add(self.sma.Current.Value)
    
    @property
    def ready(self):
        return all((
            self.sma.IsReady,
            self.sma_volume.IsReady,
            self.sma_200.IsReady,
            self.atr.IsReady,
            self.trade_bar_window.IsReady,
            self.max_volume.IsReady,
            self.max_price.IsReady,
            self.sma_window.IsReady,
        ))
    
    @property
    def max_vol_on_down_day(self):
        max_vol = 0
        for i in range(0, 10):
            trade_bar = self.trade_bar_window[i]
            if trade_bar.Close < trade_bar.Open:
                max_vol = max(max_vol, trade_bar.Volume)
        return max_vol
    
    def atrp(self, close):
        return (self.atr.Current.Value / close) * 100
    
    @property
    def uptrending(self):
        return self.sma.Current.Value > self.sma_200.Current.Value


class Breakout(QCAlgorithm):
    def Initialize(self):
        self.SetStartDate(2021, 1, 1)
        self.SetEndDate(2021, 11, 1)
        self.SetCash(10000)
        self.SetWarmUp(timedelta(200), Resolution.Daily)
        self.UniverseSettings.Resolution = Resolution.Daily
        self.SetBrokerageModel(BrokerageName.InteractiveBrokersBrokerage)
        self.EQUITY_RISK_PC = 0.01
        self.AddUniverse(self.coarse_selection)
        self.symbol_map = {}
        self.screened_symbols = []
        self.AddEquity("SPY", Resolution.Daily)
        self.SYMBOLS_URL = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vRajMcf0SW61y_kCO9s1mhvCxGlGq9PgSRyQyNyQCx9ALfOF800f22Z0OKkL_-PU_jBWowdOBkM6FtM/pub?gid=0&single=true&output=csv'
        self.Schedule.On(
            self.DateRules.EveryDay("SPY"),
            self.TimeRules.AfterMarketOpen("SPY", -10),
            self.update_screened_symbols
        )
        # self.screened_symbols = ["ASAN", "TSLA", "RBLX", "DOCN", "FTNT", "DDOG", "NET", "BILL", "NVDA", "AMBA", "INMD", "AMEH", "AEHR", "SITM", "CROX"]
    
    def live_log(self, msg):
        if self.LiveMode:
            self.Log(msg)

    def coarse_selection(self, coarse):
        return [stock.Symbol for stock in coarse if stock.Price >= 10 and stock.Market == Market.USA and stock.HasFundamentalData]

    def OnData(self, data):
        symbols = []
        for symbol in self.ActiveSecurities.Keys:
            if symbol.Value not in self.screened_symbols:
                continue
            if not data.Bars.ContainsKey(symbol):
                continue
            if symbol not in self.symbol_map:
                self.symbol_map[symbol] = SymbolIndicators(
                    self.History(symbol, 200, Resolution.Daily)
                )
            else:
                self.symbol_map[symbol].update(data.Bars[symbol])
            if not self.symbol_map[symbol].ready:
                continue
            if self.sell_signal(symbol, data):
                self.Liquidate(symbol)
            if self.symbol_map[symbol].uptrending:
                symbols.append(symbol)
        if self.IsWarmingUp:
            return
        self.live_log("processing on data")
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
    
    def buy(self, symbol, order_tag=None):
        position_size = round((self.Portfolio.TotalPortfolioValue * self.EQUITY_RISK_PC) / self.symbol_map[symbol].atr.Current.Value)
        position_value = position_size * self.ActiveSecurities[symbol].Price
        self.live_log(f"buying {symbol.Value}")
        if position_value < self.Portfolio.Cash:
            self.MarketOrder(symbol, position_size, tag=order_tag)
        else:
            self.live_log(f"insufficient cash ({self.Portfolio.Cash}) to purchase {symbol.Value}")
    
    def sell_signal(self, symbol, slice):
        profit = self.Portfolio[symbol].UnrealizedProfitPercent
        return profit >= 0.20 or profit <= -0.05
    
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
        # highest vol in 200 days
        if not indicators.max_volume.Current.Value == trade_bar_lts.Volume:
            return False
        # closing range PC above 75; formula = ((close - low) / ((high - low) / 100))
        if not ((trade_bar_lts.Close - trade_bar_lts.Low) / ((trade_bar_lts.High - trade_bar_lts.Low) / 100)) >= 75:
            return False
        if not ((indicators.max_price.Current.Value - trade_bar_lts.High) / indicators.max_price.Current.Value) <= 0.2:
            return False
        return True
    
    def inside_day(self, symbol):
        """
        · Inside Day (today's whole price bar within yesterday's)
        · Below-average volume
        · Tight chart pattern previous to today (ATRP may be required for this)
        Entry: The prior day's high or the nearest longer-term breakout level.

        Exit: Inside Day's low.

        The goal is to keep risk manageable with a 3-5% stop (and less if possible!)
        """
        indicators: SymbolIndicators = self.symbol_map[symbol]
        trade_bar_lts = indicators.trade_bar_window[0]
        trade_bar_prev = indicators.trade_bar_window[1]
        # inside day
        if not ((trade_bar_lts.High < trade_bar_prev.High) and (trade_bar_lts.Low > trade_bar_prev.Low)):
            return False
        # below avg vol
        if trade_bar_lts.Volume > indicators.sma_volume.Current.Value:
            return False
        # ensure positive close
        if trade_bar_lts.Open > trade_bar_lts.Close:
            return False
        return True
    
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
        if indicators.max_price.PeriodsSinceMaximum > 15:
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
        if trade_bar_lts.Low > indicators.sma_window[0]:
            return False
        return True
    
    def update_screened_symbols(self):
        if self.IsWarmingUp:
            return
        if not self.screened_symbols or self.LiveMode:
            self.screened_symbols = self.Download(self.SYMBOLS_URL).split("\r\n")
            self.live_log(f"symbols updated: {','.join(self.screened_symbols)}")
