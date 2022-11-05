from AlgorithmImports import *
import base64


class BaseBuyer(QCAlgorithm):
    
    def Initialize(self):
        self.SetStartDate(2019, 1, 1)
        self.SetEndDate(2020, 1, 1)
        self.stocks_map = {}
        self.open_positions = {}
        self.stocks_file_link = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vS_oVGJKqa6xhMcNKG3k5TkK_uXX_GSYvK6GZBqagd8hj1xqk0ONdavJrkl4KWYsomtFFMddD6hO2b5/pubhtml?gid=0&single=true'
        self.backtest_stocks_file_link = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vSujpOFMXOFM9pnjLa8-3kHJqYRSnCeh5ZWkR08HRFi5Xcf018-LQYCG6Pf_OwZFQ-rtTPtcP1Zu2sM/pub?gid=0&single=true&output=csv'
        self.EQUITY_RISK_PC = 0.75
        self.UniverseSettings.Resolution = Resolution.Daily
        # Order margin value has to have a minimum of 0.5% of Portfolio value, allows filtering out small trades and reduce fees.
        self.Settings.MinimumOrderMarginPortfolioPercentage = 0.005
        self.AddUniverse("my-dropbox-universe", self.universe_selector)

    def universe_selector(self, date):
        csv_str = self.Download(self.stocks_file_link if self.LiveMode else self.backtest_stocks_file_link)
        for index, line in enumerate(csv_str.splitlines()):
            row = line.split(',')
            if index == 0 or len(row) < 3:
                continue
            symbol = row[0].strip()
            pivot = float(row[1])
            stop = float(row[2])
            if symbol and pivot and stop:
                self.stocks_map[symbol] = {
                    'pivot': pivot,
                    'stop': stop
                }
        return list(self.stocks_map.keys())

    def OnData(self, slice):
        if slice.Bars.Count == 0:
            return
        for symbol in self.ActiveSecurities.Keys:
            if self.ActiveSecurities[symbol].Invested:
                if self.Portfolio[symbol].UnrealizedProfitPercent >= 0.20 or self.position_outdated(symbol):
                    self.Liquidate(symbol)
            else:
                pivot = self.stocks_map[str(symbol)]['pivot']
                stock_in_buy_range = self.ActiveSecurities[symbol].Close > pivot < pivot * 1.05
                if not stock_in_buy_range:
                    continue
                atr = AverageTrueRange(21)
                vol_ma = RelativeDailyVolume(symbol, 50)
                for data in self.History(symbol, 50, Resolution.Daily).itertuples():
                    trade_bar = TradeBar(data.Index[1], data.Index[0], data.open, data.high, data.low, data.close, data.volume, timedelta(1))
                    atr.Update(trade_bar)
                    vol_ma.Update(trade_bar)
                if vol_ma.Current.Value > 1:
                    position_size = self.calculate_position_size(atr.Current.Value)
                    position_value = position_size * self.ActiveSecurities[symbol].Price
                    if position_value < self.Portfolio.Cash:
                        self.MarketOrder(symbol, position_size)
                        self.open_positions[symbol] = self.Time

    def calculate_position_size(self, atr):
        return round((self.Portfolio.TotalPortfolioValue * self.EQUITY_RISK_PC) / atr)
