import datetime
from AlgorithmImports import *


class MeanReversionAlpha(AlphaModel):
    def __init__(self, *args, **kwargs):
        self.resolution = Resolution.Daily
        self.prediction_interval = Time.Multiply(Extensions.ToTimeSpan(Resolution.Daily), 5)
        self.symbols = {}
        self.equity_risk_pc = kwargs['equity_risk_pc']
        self.adx_lookback = kwargs['adx_lookback']
        self.atr_lookback = kwargs['atr_lookback']
        self.rsi_lookback = kwargs['rsi_lookback']
        self.sma_lookback = kwargs['sma_lookback']
        self.direction = kwargs['direction']
    
    def Update(self, algorithm, data):
        securities = self.get_long_securities(algorithm, data) if self.direction == InsightDirection.Up else self.get_short_securities(algorithm, data)
        return [self.get_insight(algorithm, data, symbol) for symbol in securities]
    
    def get_long_securities(self, algorithm, data):
        """
        RULES
        #1. close above 150 day: stage 2 uptrend
        #2. ADX greater than 45: strong uptrend
        #3. ATR greater than 4%: high volatility
        #4. RSI below 30: oversold
        #5. rank by most oversold RSI
        #6. filter out 10 stocks
        """
        securities = [symbol for symbol in self.symbols.keys() \
                if data.ContainsKey(symbol) and data[symbol] is not None \
                    and self.symbols[symbol].sma.Current.Value < data[symbol].Close \
                        and self.symbols[symbol].adx.Current.Value > 45 \
                            and self.symbols[symbol].atrp(data[symbol].Close) > 4 \
                                and self.symbols[symbol].rsi.Current.Value < 30]
        return sorted(
            securities, 
            key=lambda symbol: self.symbols[symbol].rsi.Current.Value, 
        )[:10]
    
    def get_short_securities(self, algorithm, data):
        """
        RULES
        #1. ADX greater than 50: strong uptrend
        #2. ATR greater than 5%: high volatility
        #3. RSI above 85: overbought
        #4. rank by most overbought RSI
        #5. filter out 10 stocks
        """
        securities = [symbol for symbol in self.symbols.keys() \
                if data.ContainsKey(symbol) and data[symbol] is not None \
                    and self.symbols[symbol].adx.Current.Value > 50 \
                        and self.symbols[symbol].atrp(data[symbol].Close) > 5 \
                            and self.symbols[symbol].rsi.Current.Value > 85]
        return sorted(
            securities, 
            key=lambda symbol: self.symbols[symbol].rsi.Current.Value,
            reverse=True, 
        )[:10]

    def OnSecuritiesChanged(self, algorithm, changes):
        for added in changes.AddedSecurities:
            self.symbols[added.Symbol] = SymbolData(
                algorithm, added, self.resolution, adx_lookback=self.adx_lookback, 
                atr_lookback=self.atr_lookback, rsi_lookback=self.rsi_lookback,
                sma_lookback=self.sma_lookback,
            )

        for removed in changes.RemovedSecurities:
            data = self.symbols.pop(removed.Symbol, None)
            if data is not None:
                algorithm.SubscriptionManager.RemoveConsolidator(removed.Symbol, data.Consolidator)
    
    def get_insight(self, algorithm, data, symbol):
        confidence = self.get_confidence_for_symbol(algorithm, data, symbol)
        return Insight(symbol, self.prediction_interval, InsightType.Price, self.direction, confidence, None)

    def get_confidence_for_symbol(self, algorithm, data, symbol):
        position_size = (algorithm.Portfolio.TotalPortfolioValue * self.equity_risk_pc) / self.symbols[symbol].atr.Current.Value
        position_value = position_size * data[symbol].Close
        return position_value / algorithm.Portfolio.TotalPortfolioValue


class SymbolData:
    def __init__(self, algorithm, security, resolution, adx_lookback = 7, atr_lookback = 10, rsi_lookback = 3, sma_lookback = 150):
        self.security = security
        self.adx = AverageDirectionalIndex(adx_lookback)
        self.atr = AverageTrueRange(atr_lookback)
        self.rsi = RelativeStrengthIndex(rsi_lookback)
        self.sma = SimpleMovingAverage(sma_lookback)
        self.Consolidator = algorithm.ResolveConsolidator(security.Symbol, resolution)
        algorithm.RegisterIndicator(security.Symbol, self.adx, self.Consolidator)
        algorithm.RegisterIndicator(security.Symbol, self.atr, self.Consolidator)
        algorithm.RegisterIndicator(security.Symbol, self.rsi, self.Consolidator)
        algorithm.RegisterIndicator(security.Symbol, self.sma, self.Consolidator)
        algorithm.WarmUpIndicator(security.Symbol, self.adx, resolution)
        algorithm.WarmUpIndicator(security.Symbol, self.atr, resolution)
        algorithm.WarmUpIndicator(security.Symbol, self.rsi, resolution)
        algorithm.WarmUpIndicator(security.Symbol, self.sma, resolution)

    def atrp(self, close):
        return (self.atr.Current.Value / close) * 100


class LongShortMeanReversion(QCAlgorithm):
    def Initialize(self):
        self.SetStartDate(2020, 1, 1)
        self.SetCash(100000)
        self.SetWarmUp(timedelta(200), Resolution.Daily)
        self.UniverseSettings.Resolution = Resolution.Daily
        self.SetBrokerageModel(BrokerageName.InteractiveBrokersBrokerage)
        self.SetUniverseSelection(QC500UniverseSelectionModel())
        self.EQUITY_RISK_PC = 0.01
        self.SetAlpha(
            CompositeAlphaModel(
                MeanReversionAlpha(direction=InsightDirection.Up, equity_risk_pc=self.EQUITY_RISK_PC, adx_lookback=7, atr_lookback=10, rsi_lookback=3, sma_lookback=150),
                MeanReversionAlpha(direction=InsightDirection.Down, equity_risk_pc=self.EQUITY_RISK_PC, adx_lookback=7, atr_lookback=10, rsi_lookback=3, sma_lookback=150),
            )
        )
        # rebalance every Sunday & Wednesday
        self.SetPortfolioConstruction(EqualWeightingPortfolioConstructionModel(self.DateRules.Every([0, 3])))
        self.SetExecution(ImmediateExecutionModel())
        self.Settings.RebalancePortfolioOnInsightChanges = False
        self.Settings.RebalancePortfolioOnSecurityChanges = False
        self.AddRiskManagement(MaximumDrawdownPercentPerSecurity(0.2))
        self.AddRiskManagement(MaximumUnrealizedProfitPercentPerSecurity(0.05))

