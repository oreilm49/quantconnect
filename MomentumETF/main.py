from AlgorithmImports import *


class SymbolIndicators:
    def __init__(self, history) -> None:
        self.bollinger = BollingerBands(21, 2)
        self.keltner = KeltnerChannels(21, 2)
        self.donchian = DonchianChannel(21, 2)
        self.mfi = MoneyFlowIndex(5)
        self.atr = AverageTrueRange(21)

        for data in history.itertuples():
            trade_bar = TradeBar(data.Index[1], data.Index[0], data.open, data.high, data.low, data.close, data.volume, timedelta(1))
            self.update(trade_bar)
        
    def update(self, trade_bar):
        self.bollinger.Update(trade_bar.EndTime, trade_bar.Close)
        self.keltner.Update(trade_bar)
        self.donchian.Update(trade_bar)
        self.mfi.Update(trade_bar)
        self.atr.Update(trade_bar)
    
    @property
    def ready(self):
        return all((
            self.bollinger.IsReady,
            self.keltner.IsReady,
            self.donchian.IsReady,
            self.mfi.IsReady,
            self.atr.IsReady,
        ))
    
    @property
    def lowest_upper_band(self):
        return min((
            self.bollinger.UpperBand.Current.Value,
            self.keltner.UpperBand.Current.Value,
            self.donchian.UpperBand.Current.Value,
        ))
    
    @property
    def highest_lower_band(self):
        return max((
            self.bollinger.LowerBand.Current.Value,
            self.keltner.LowerBand.Current.Value,
            self.donchian.LowerBand.Current.Value,
        ))


class MomentumETF(QCAlgorithm):
    def Initialize(self):
        self.SetStartDate(2019, 1, 1)
        self.SetEndDate(2022, 11, 1)
        self.SetCash(100000)
        self.UniverseSettings.Resolution = Resolution.Daily
        self.EQUITY_RISK_PC = 0.01
        tickers = [
            "GXLE",
            "GXLK",
            "GXLV",
            "GXLF",
            "SXLP",
            "SXLI",
            "GXLC",
            "SXLY",
            "SXLB",
            "SXLU",
        ] if self.LiveMode else [
            "XLE",
            "XLK",
            "XLV",
            "XLF",
            "XLP",
            "XLI",
            "XLC",
            "XLY",
            "XLB",
            "XLU",
        ]
        self.symbol_map = {}
        for ticker in tickers:
            self.AddEquity(ticker, Resolution.Daily)

    def OnData(self, slice):
        uninvested = []
        for symbol in self.ActiveSecurities.Keys:
            if not slice.Bars.ContainsKey(symbol):
                self.Debug("symbol not in slice")
                continue
            if symbol not in self.symbol_map:
                self.symbol_map[symbol] = SymbolIndicators(
                    self.History(symbol, 21, Resolution.Daily)
                )
            else:
                self.symbol_map[symbol].update(slice.Bars[symbol])
            if not self.symbol_map[symbol].ready:
                self.Debug("indicators not ready")
                continue
            if not self.ActiveSecurities[symbol].Invested:
                uninvested.append(symbol)
            else:
                highest_lower_band = self.symbol_map[symbol].highest_lower_band
                mfi_oversold = self.symbol_map[symbol].mfi.Current.Value <= 20
                if slice.Bars[symbol].Low <= highest_lower_band and mfi_oversold:
                    self.Liquidate(symbol)
        uninvested = sorted(
            uninvested, 
            key=lambda symbol: self.symbol_map[symbol].mfi.Current.Value, 
            reverse=True,
        )
        for symbol in uninvested:
            if not self.symbol_map[symbol].mfi.Current.Value >= 80:
                continue
            self.Debug(f"overbought: {self.ActiveSecurities[symbol].Price} {self.symbol_map[symbol].lowest_upper_band}")
            if self.ActiveSecurities[symbol].Price >= self.symbol_map[symbol].lowest_upper_band:
                position_size = self.calculate_position_size(self.symbol_map[symbol].atr.Current.Value)
                position_value = position_size * self.ActiveSecurities[symbol].Price
                if position_value < self.Portfolio.Cash:
                    self.MarketOrder(symbol, position_size)
    
    def calculate_position_size(self, atr):
        return round((self.Portfolio.TotalPortfolioValue * self.EQUITY_RISK_PC) / atr)
