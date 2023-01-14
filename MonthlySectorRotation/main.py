import datetime
from AlgorithmImports import RateOfChangePercent, SharpeRatio, AverageTrueRange, AlphaModel, Extensions, Resolution,\
    Time, InsightDirection, InsightType, Insight, SimpleMovingAverage, RollingWindow, QCAlgorithm, BrokerageName, \
    CompositeAlphaModel, ImmediateExecutionModel, NullRiskManagementModel, ConfidenceWeightedPortfolioConstructionModel


class SymbolData:
    def __init__(self, algorithm, security, resolution, roc_fast_lookback = None, roc_slow_lookback = None, atr_lookback = None, sharpe_lookback = None, sma_lookback = None):
        self.security = security
        self.symbol = security.Symbol
        self.algorithm = algorithm
        self.indicators = []
        self.consolidator = algorithm.ResolveConsolidator(security.Symbol, resolution)
        if atr_lookback:
            self.atr = AverageTrueRange(atr_lookback)
            self.indicators.append(self.atr)
        if roc_fast_lookback:
            self.roc_fast = RateOfChangePercent(roc_fast_lookback)
            self.indicators.append(self.roc_fast)
        if roc_slow_lookback:
            self.roc_slow = RateOfChangePercent(roc_slow_lookback)
            self.indicators.append(self.roc_slow)
        if sharpe_lookback:
            self.sharpe = SharpeRatio(sharpe_lookback)
            self.indicators.append(self.sharpe)
        if sma_lookback:
            self.sma = SimpleMovingAverage(sma_lookback)
            self.indicators.append(self.sma)
        for indicator in self.indicators:
            algorithm.RegisterIndicator(security.Symbol, indicator, self.consolidator)
            algorithm.WarmUpIndicator(security.Symbol, indicator, resolution)

    def dispose(self):
        self.algorithm.SubscriptionManager.RemoveConsolidator(self.symbol, self.consolidator)
        
    @property
    def monthly_performance(self) -> float:
        return self.roc_fast.Current.Value + (-2 * self.roc_slow.Current.Value)
    
    @property
    def ready(self) -> bool:
        return all([indicator.IsReady for indicator in self.indicators])
    
    def __str__(self) -> str:
        values = ",".join([str(indicator) for indicator in self.indicators])
        return f"{self.security.Symbol} ({values})"
    

class BaseAlpha(AlphaModel):
    def __init__(self, *args, **kwargs):
        self.equity_risk_pc = kwargs['equity_risk_pc']
        self.resolution = kwargs['resolution']
        self.month = None
        self.indicators_map = {}
        self.symbols = kwargs['symbols']
        self.prediction_interval = Time.Multiply(Extensions.ToTimeSpan(self.resolution), 5) ## Arbitrary
        self.indicator_kwargs = kwargs['indicator_kwargs']
        self.spy = kwargs['spy']
        self.spy_data = None

    def get_confidence_for_symbol(self, algorithm, data, symbol):
        algorithm.Debug(f"{algorithm.Time}: {self.indicators_map[symbol]}")
        position_size = (algorithm.Portfolio.TotalPortfolioValue * self.equity_risk_pc) / self.indicators_map[symbol].atr.Current.Value
        position_value = position_size * data[symbol].Close
        return position_value / algorithm.Portfolio.TotalPortfolioValue
    
    def get_insight(self, algorithm, data, symbol, direction = InsightDirection.Up):
        confidence = self.get_confidence_for_symbol(algorithm, data, symbol)
        return Insight(symbol, self.prediction_interval, InsightType.Price, direction, confidence, None)
    
    def OnSecuritiesChanged(self, algorithm, changes):
        for added in changes.AddedSecurities:
            if added.Symbol == self.spy:
                self.spy_data = SymbolData(
                    algorithm, added, self.resolution, **dict(sma_lookback=150)
                )
            else:
                self.indicators_map[added.Symbol] = SymbolData(
                    algorithm, added, self.resolution, **self.indicator_kwargs
                )

        for removed in changes.RemovedSecurities:
            data = self.indicators_map.pop(removed.Symbol, None)
            if data is not None:
                data.dispose()
    

class MonthlyRotation(BaseAlpha):
    """
    A U.S. sector rotation Momentum Strategy with a long lookback period
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.num = kwargs['num']

    def Update(self, algorithm, data):
        if algorithm.Time.month == self.month or algorithm.IsWarmingUp:
            return []
        self.month = algorithm.Time.month
        highest_sharpe = sorted(
            self.symbols, 
            key=lambda symbol: self.indicators_map[symbol].sharpe.Current.Value, 
            reverse=True,
        )[:self.num]
        # risk management
        if data.ContainsKey(self.spy) and data[self.spy] is not None and self.spy_data:
            if data[self.spy].Close < self.spy_data.sma.Current.Value:
                return [self.get_insight(algorithm, data, symbol, InsightDirection.Flat) for symbol in self.symbols]
        return [self.get_insight(algorithm, data, symbol) for symbol in highest_sharpe]
            

class BuyTheWorstMeanReversion(BaseAlpha):
    def Update(self, algorithm, data):
        if algorithm.Time.month == self.month or algorithm.IsWarmingUp:
            return []
        self.month = algorithm.Time.month
        worst_performer = sorted(
            self.symbols,
            key=lambda symbol: self.indicators_map[symbol].monthly_performance, 
            reverse=True,
        )[0]
        return [self.get_insight(algorithm, data, worst_performer)]    


class Hedge(AlphaModel):
    """
    Buys the short spy when spy flashes a sell signal
    """
    def __init__(self, *args, **kwargs):
        self.WINDOW_LENGTH = 30
        self.spy = kwargs['spy']
        self.hedge = kwargs['hedge']
        self.ma = SimpleMovingAverage(50)
        self.ema = SimpleMovingAverage(30)
        self.close_window = RollingWindow[float](self.WINDOW_LENGTH)
        self.ema_window = RollingWindow[float](self.WINDOW_LENGTH)
        self.ma_window = RollingWindow[float](self.WINDOW_LENGTH)
        self.prediction_interval = Time.Multiply(Extensions.ToTimeSpan(Resolution.Daily), 5) ## Arbitrary
        self.month = None

    def Update(self, algorithm, data):
        if not data.ContainsKey(self.spy) or data[self.spy] is None:
            return []
        self.ma.Update(data[self.spy].EndTime, data[self.spy].Close)
        self.ema.Update(data[self.spy].EndTime, data[self.spy].Close)
        if not all([self.ma.IsReady, self.ema.IsReady]):
            return []
        self.close_window.Add(data[self.spy].Close)
        self.ema_window.Add(self.ema.Current.Value)
        self.ma_window.Add(self.ma.Current.Value)
        if not all([self.close_window.IsReady, self.ema_window.IsReady, self.ma_window.IsReady]):
            return []
        if algorithm.Time.month == self.month:
            return []
        self.month = algorithm.Time.month
        """
        Hedge active:
        - price is below sma
        - price closes below ema
        """
        hedge_invested = algorithm.ActiveSecurities[self.hedge].Invested
        direction = None
        for i in range(1, self.WINDOW_LENGTH):
            hedge_off = self.close_window[i] > self.ma_window[i] or\
                    all([self.close_window[i + j] > self.ema_window[i + j] for j in [0, 1]])
            if hedge_off:
                if hedge_invested:
                    direction = InsightDirection.Flat
                break
            hedge_on = self.close_window[i] < self.ma_window[i] and self.close_window[i] < self.ema_window[i]
            if hedge_on:
                if not hedge_invested:
                    direction = InsightDirection.Up
                break
        if direction is None:
            return []
        return [Insight(self.hedge, self.prediction_interval, InsightType.Price, direction, None, None)]


class MonthlySectorRotation(QCAlgorithm):
    def Initialize(self):
        self.SetStartDate(2002, 1, 1)
        self.SetEndDate(2022, 11, 1)
        self.SetCash(10000)
        self.resolution = Resolution.Daily
        self.SetWarmUp(datetime.timedelta(200), self.resolution)
        self.UniverseSettings.Resolution = self.resolution
        self.SetBrokerageModel(BrokerageName.InteractiveBrokersBrokerage)
        self.Settings.RebalancePortfolioOnInsightChanges = False
        self.Settings.RebalancePortfolioOnSecurityChanges = False
        self.equity_risk_pc = 0.02
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
        hedge_tickers = ["", ""] if self.LiveMode else ["SPY", "SH"]
        symbols = [self.AddEquity(ticker, self.resolution).Symbol for ticker in tickers]
        spy = self.AddEquity(hedge_tickers[0], self.resolution).Symbol
        alpha_kwargs = dict(
            resolution=self.resolution,
            equity_risk_pc=self.equity_risk_pc,
            symbols=symbols,
            spy=spy,
        )
        self.SetAlpha(
            CompositeAlphaModel(
                MonthlyRotation(**alpha_kwargs, num=1, indicator_kwargs=dict(sharpe_lookback=198, atr_lookback=21)),
                MonthlyRotation(**alpha_kwargs, num=1, indicator_kwargs=dict(sharpe_lookback=7, atr_lookback=21)),
                BuyTheWorstMeanReversion(**alpha_kwargs, indicator_kwargs=dict(
                    roc_fast_lookback=10, roc_slow_lookback=20, atr_lookback=21
                )),
                Hedge(
                    spy=self.AddEquity(hedge_tickers[0], Resolution.Daily).Symbol,
                    hedge=self.AddEquity(hedge_tickers[1], Resolution.Daily).Symbol,
                )
            )
        )
        self.SetPortfolioConstruction(ConfidenceWeightedPortfolioConstructionModel(self.DateRules.MonthEnd()))
        self.SetExecution(ImmediateExecutionModel())
        self.SetRiskManagement(NullRiskManagementModel())
