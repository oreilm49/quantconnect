import datetime
from AlgorithmImports import Resolution, AverageTrueRange, SimpleMovingAverage, MoneyFlowIndex,\
    BrokerageName, QCAlgorithm, QC500UniverseSelectionModel, ImmediateExecutionModel, Field


class TurleTrading(QCAlgorithm):
    def Initialize(self):
        self.SetStartDate(2021, 1, 1)
        self.SetCash(100000)
        self.resolution = Resolution.Daily
        self.SetWarmUp(datetime.timedelta(200), self.resolution)
        self.UniverseSettings.Resolution = self.resolution
        self.SetBrokerageModel(BrokerageName.InteractiveBrokersBrokerage)
        self.SetUniverseSelection(QC500UniverseSelectionModel())
        self.SetExecution(ImmediateExecutionModel())
        self.symbols = {}
        self.EQUITY_RISK_PC = 0.02
        self.mfi_lookback = 21
        self.atr_lookback = 21
        self.sma_lookback = 150
        self.high_lookback = 40
        self.low_lookback = 20


    def OnSecuritiesChanged(self, changes):
        for added in changes.AddedSecurities:
            self.symbols[added.Symbol] = SymbolData(
                self, added, self.resolution, mfi_lookback=self.mfi_lookback,
                atr_lookback=self.atr_lookback, sma_lookback=self.sma_lookback,
                high_lookback=self.high_lookback, low_lookback=self.low_lookback,
            )

        for removed in changes.RemovedSecurities:
            data = self.symbols.pop(removed.Symbol, None)
            if data is not None:
                self.SubscriptionManager.RemoveConsolidator(removed.Symbol, data.Consolidator)

    def OnData(self, data):
        securities = [
            symbol for symbol in self.symbols.keys() \
            if self.symbols[symbol].sma.Current.Value < self.ActiveSecurities[symbol].Close \
            and self.symbols[symbol].high.PeriodsSinceMaximum >= self.high_lookback -1 \
            and not self.ActiveSecurities[symbol].Invested
        ]
        securities = sorted(
            securities, 
            key=lambda symbol: self.symbols[symbol].mfi.Current.Value,
            reverse=True,
        )[:10]
        for symbol in securities:
            position_size = self.calculate_position_size(symbol)
            position_value = position_size * self.ActiveSecurities[symbol].Price
            if position_value < self.Portfolio.Cash:
                self.MarketOrder(symbol, position_size)
        self.handle_exit_strategy()

    def handle_exit_strategy(self):
        for symbol in self.symbols.keys():
            if not self.ActiveSecurities[symbol].Invested:
                continue
            if symbol not in self.symbols:
                self.Liquidate(symbol)
            close = self.ActiveSecurities[symbol].Close
            if close < self.symbols[symbol].low.Current.Value:
                self.Liquidate(symbol)
            if self.Portfolio[symbol].UnrealizedProfitPercent >= 0.20 or \
                self.Portfolio[symbol].UnrealizedProfitPercent <= -0.08 or \
                    close < self.symbols[symbol].sma.Current.Value:
                self.Liquidate(symbol)
    
    def calculate_position_size(self, symbol):
        atr = self.symbols[symbol].atr.Current.Value
        return round((self.Portfolio.TotalPortfolioValue * self.EQUITY_RISK_PC) / atr)


class SymbolData:
    def __init__(self, algorithm, security, resolution, mfi_lookback = 3, atr_lookback = 10, sma_lookback = 150, high_lookback = 40, low_lookback = 40):
        self.security = security
        self.mfi = MoneyFlowIndex(mfi_lookback)
        self.atr = AverageTrueRange(atr_lookback)
        self.sma = SimpleMovingAverage(sma_lookback)
        self.high = algorithm.MAX(self.security.Symbol, high_lookback, resolution, Field.High)
        self.low = algorithm.MIN(self.security.Symbol, low_lookback, resolution, Field.Low)
        self.Consolidator = algorithm.ResolveConsolidator(security.Symbol, resolution)
        for indicator in (self.mfi, self.atr, self.sma):
            algorithm.RegisterIndicator(security.Symbol, indicator, self.Consolidator)
            algorithm.WarmUpIndicator(security.Symbol, indicator, resolution)
