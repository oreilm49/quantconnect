from AlgorithmImports import *
import datetime

class BaseBuyer(QCAlgorithm):
    
    def Initialize(self):
        self.SetStartDate(2019, 1, 1)
        self.SetEndDate(2020, 1, 1)
        self.stocks_map = {}
        self.stocks_file_link = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vS_oVGJKqa6xhMcNKG3k5TkK_uXX_GSYvK6GZBqagd8hj1xqk0ONdavJrkl4KWYsomtFFMddD6hO2b5/pubhtml?gid=0&single=true'
        self.backtest_stocks_file_link = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vSujpOFMXOFM9pnjLa8-3kHJqYRSnCeh5ZWkR08HRFi5Xcf018-LQYCG6Pf_OwZFQ-rtTPtcP1Zu2sM/pub?gid=0&single=true&output=csv'
        self.EQUITY_RISK_PC = 0.01
        self.UniverseSettings.Resolution = Resolution.Hour
        # Order margin value has to have a minimum of 0.5% of Portfolio value, allows filtering out small trades and reduce fees.
        self.Settings.MinimumOrderMarginPortfolioPercentage = 0.005
        self.AddUniverse("my-dropbox-universe", self.universe_selector)
        self.csv_str = None
    
    def get_csv_str(self):
        if self.LiveMode:
            return self.Download(self.stocks_file_link)
        if self.csv_str:
            return self.csv_str
        self.csv_str = self.Download(self.backtest_stocks_file_link)
        return self.csv_str

    def universe_selector(self, date):
        csv_str = self.get_csv_str()
        for index, line in enumerate(csv_str.splitlines()):
            row = line.split(',')
            if index == 0 or len(row) < 3:
                continue
            try:
                symbol = row[0].strip()
                pivot = float(row[1])
                stop = float(row[2])
                if symbol and pivot and stop:
                    self.stocks_map[symbol] = {
                        'pivot': pivot,
                        'stop': stop
                    }
            except:
                continue
        return list(self.stocks_map.keys())

    def OnData(self, slice):
        if slice.Bars.Count == 0:
            return
        for symbol in self.ActiveSecurities.Keys:
            if symbol.Value not in self.stocks_map:
                continue

            # initialize volume indicator
            symbol_history = None
            if 'vol_ma' not in self.stocks_map[symbol.Value]:
                vol_ma = SimpleMovingAverage(300)
                for data in self.History(symbol, 300, Resolution.Hour).itertuples():
                    vol_ma.Update(data.Index[1], data.volume)
                self.stocks_map[symbol.Value]['vol_ma'] = vol_ma
            self.stocks_map[symbol.Value]['vol_ma'].Update(self.Time, slice.Bars[symbol].Volume)

            # buy / sell logic
            if self.ActiveSecurities[symbol].Invested:
                if self.Portfolio[symbol].UnrealizedProfitPercent >= 0.20:
                    self.Liquidate(symbol)
            else:
                pivot = self.stocks_map[symbol.Value]['pivot']
                stock_in_buy_range = self.ActiveSecurities[symbol].Close > pivot < pivot * 1.05
                if not stock_in_buy_range:
                    continue
                if not slice.Bars[symbol].Close > slice.Bars[symbol].Open:
                    continue
                vol = self.stocks_map[symbol.Value]['vol_ma']
                if vol.IsReady and slice.Bars[symbol].Volume > vol.Current.Value:
                    self.Debug(f"{symbol.Value} vol {vol.Current.Value}")
                    atr = AverageTrueRange(21)
                    symbol_history = symbol_history or self.History(symbol, 21, Resolution.Daily).itertuples()
                    for data in symbol_history:
                        atr.Update(
                            TradeBar(data.Index[1], symbol, data.open, data.high, data.low, data.close, data.volume, datetime.timedelta(days=1)))
                    position_size = self.calculate_position_size(atr.Current.Value)
                    position_value = position_size * self.ActiveSecurities[symbol].Price
                    if position_value < self.Portfolio.Cash:
                        self.MarketOrder(symbol, position_size)
                        self.StopMarketOrder(symbol, -1 * position_size, self.stocks_map[symbol.Value]['stop'])

    def calculate_position_size(self, atr):
        return round((self.Portfolio.TotalPortfolioValue * self.EQUITY_RISK_PC) / atr)
