from AlgorithmImports import *


class BaseAlphaModel(AlphaModel):
    def __init__(self, *args, **kwargs):
        self.month = None
        self.prediction_interval = Time.Multiply(Extensions.ToTimeSpan(Resolution.Daily), 5)
        self.symbols = {}
        self.spy = kwargs['spy']
        self.equity_risk_pc = kwargs['equity_risk_pc']
        self.spy_data = None
        self.resolution = Resolution.Daily
        self.last_month = -1

    def get_confidence_for_symbol(self, algorithm, data, symbol):
        position_size = (algorithm.Portfolio.TotalPortfolioValue * self.equity_risk_pc) / self.symbols[symbol].atr.Current.Value
        position_value = position_size * data[symbol].Close
        return position_value / algorithm.Portfolio.TotalPortfolioValue

    def spy_downtrending(self, algorithm, data):
        if self.spy_data is None:
            self.spy_data = SpyData(algorithm, self.spy, self.resolution)
        if data.ContainsKey(self.spy) and data[self.spy] is not None:
            return data[self.spy].Close < self.spy_data.ma.Current.Value
        algorithm.Debug("SPY not in data")
        return True


class MonthlyRateOfChangeTrendFollowingAlpha(BaseAlphaModel):
    def Update(self, algorithm, data):
        if algorithm.Time.month == self.last_month:
            return []
        if self.spy_downtrending(algorithm, data):
            return []
        self.last_month = algorithm.Time.month 
        securities = [symbol for symbol in self.symbols.keys() \
                if data.ContainsKey(symbol) and data[symbol] is not None \
                    and self.symbols[symbol].atrp(data[symbol].Close) <= 5]
        top_performers = sorted(
            securities, 
            key=lambda symbol: self.symbols[symbol].roc.Current.Value, 
            reverse=True,
        )[:10]
        return [self.get_insight(algorithm, data, symbol) for symbol in top_performers]

    def OnSecuritiesChanged(self, algorithm, changes):
        for added in changes.AddedSecurities:
            self.symbols[added.Symbol] = MonthlyRateOfChangeTrendFollowingData(algorithm, added, self.resolution)

        for removed in changes.RemovedSecurities:
            data = self.symbols.pop(removed.Symbol, None)
            if data is not None:
                algorithm.SubscriptionManager.RemoveConsolidator(removed.Symbol, data.Consolidator)
    
    def get_insight(self, algorithm, data, symbol):
        confidence = self.get_confidence_for_symbol(algorithm, data, symbol)
        return Insight(symbol, self.prediction_interval, InsightType.Price, InsightDirection.Up, confidence, None)


class MonthlyRateOfChangeTrendFollowingData:
    def __init__(self, algorithm, security, resolution):
        self.security = security
        self.roc = RateOfChangePercent(200)
        self.atr = AverageTrueRange(21)
        self.Consolidator = algorithm.ResolveConsolidator(security.Symbol, resolution)
        algorithm.RegisterIndicator(security.Symbol, self.roc, self.Consolidator)
        algorithm.RegisterIndicator(security.Symbol, self.atr, self.Consolidator)
        algorithm.WarmUpIndicator(security.Symbol, self.roc, resolution)
        algorithm.WarmUpIndicator(security.Symbol, self.atr, resolution)

    def atrp(self, close):
        return (self.atr.Current.Value / close) * 100


class SpyData:
    def __init__(self, algorithm, symbol, resolution):
        self.ma = SimpleMovingAverage(200)
        self.Consolidator = algorithm.ResolveConsolidator(symbol, resolution)
        algorithm.RegisterIndicator(symbol, self.ma, self.Consolidator)
        algorithm.WarmUpIndicator(symbol, self.ma, resolution)


class MyQC500(QC500UniverseSelectionModel):
    """
    Optimized to select the top 250 stocks by dollar volume
    """
    numberOfSymbolsCoarse = 250


class MultiNonCorrelatedAlphaStrategy(QCAlgorithm):
    def Initialize(self):
        self.SetStartDate(2020, 1, 1)
        self.SetCash(100000)
        self.SetWarmUp(timedelta(200), Resolution.Daily)
        self.UniverseSettings.Resolution = Resolution.Daily
        self.SetBrokerageModel(BrokerageName.InteractiveBrokersBrokerage)
        self.SetUniverseSelection(MyQC500())
        self.symbols = {}
        self.EQUITY_RISK_PC = 0.01
        self.spy = self.AddEquity("SPY", Resolution.Daily)
        self.SetAlpha(
            CompositeAlphaModel(
                MonthlyRateOfChangeTrendFollowingAlpha(spy=self.spy.Symbol, equity_risk_pc=self.EQUITY_RISK_PC),
            )
        )
        self.SetPortfolioConstruction(EqualWeightingPortfolioConstructionModel(self.DateRules.MonthStart()))
        self.SetExecution(ImmediateExecutionModel())
        self.SetRiskManagement(NullRiskManagementModel())
        self.Settings.RebalancePortfolioOnInsightChanges = False
        self.Settings.RebalancePortfolioOnSecurityChanges = False
