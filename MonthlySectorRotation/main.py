import datetime
from AlgorithmImports import RateOfChangePercent, SharpeRatio, AverageTrueRange, AlphaModel, Extensions, Resolution,\
    Time, InsightDirection, InsightType, Insight, SimpleMovingAverage, RollingWindow, QCAlgorithm, BrokerageName, \
    CompositeAlphaModel, ImmediateExecutionModel, NullRiskManagementModel, ConfidenceWeightedPortfolioConstructionModel


class ATRIndicators:
    def __init__(self, *args, **kwargs) -> None:
        self.atr = AverageTrueRange(21)
        
    def update(self, trade_bar):
        self.atr.Update(trade_bar)
    
    @property
    def ready(self):
        return self.atr.IsReady
    
    def __str__(self) -> str:
        return str(self.atr.Current.Value)


class RocIndicators(ATRIndicators):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.roc_10 = RateOfChangePercent(10)
        self.roc_20 = RateOfChangePercent(20)
        
    def update(self, trade_bar):
        super().update(trade_bar)
        self.roc_10.Update(trade_bar.EndTime, trade_bar.Close)
        self.roc_20.Update(trade_bar.EndTime, trade_bar.Close)
    
    @property
    def ready(self):
        return super().ready and all((
            self.roc_10.IsReady,
            self.roc_20.IsReady,
        ))
    
    @property
    def monthly_performance(self) -> float:
        return self.roc_10.Current.Value + (-2 * self.roc_20.Current.Value)


class SharpeIndicators(ATRIndicators):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.sharpe = SharpeRatio(kwargs['look_back'])
        
    def update(self, trade_bar):
        super().update(trade_bar)
        self.sharpe.Update(trade_bar.EndTime, trade_bar.Close)
    
    @property
    def ready(self):
        return super().ready and self.sharpe.IsReady
    

class BaseAlpha(AlphaModel):
    def __init__(self, *args, **kwargs) -> None:
        self.equity_risk_pc = kwargs['equity_risk_pc']

    def get_confidence_for_symbol(self, algorithm, data, symbol):
        position_size = (algorithm.Portfolio.TotalPortfolioValue * self.equity_risk_pc) / self.indicators_map[symbol].atr.Current.Value
        position_value = position_size * data[symbol].Close
        algorithm.Debug(f"CONFIDENCE: {algorithm.Time}  {str(symbol)}  {self.indicators_map[symbol]}  {algorithm.Portfolio.TotalPortfolioValue}")
        return position_value / algorithm.Portfolio.TotalPortfolioValue
    
    def get_insight(self, algorithm, data, symbol, direction = InsightDirection.Up):
        confidence = self.get_confidence_for_symbol(algorithm, data, symbol)
        # Insight(symbol, period, type, direction, magnitude=None, confidence=None, sourceModel=None, weight=None)
        return Insight(symbol, self.prediction_interval, InsightType.Price, direction, magnitude=None, confidence=confidence, sourceModel=None, weight=None)


class MonthlyRotation(BaseAlpha):
    """
    A U.S. sector rotation Momentum Strategy with a long lookback period
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.symbols = kwargs['symbols']
        self.look_back = kwargs['look_back']
        self.num = kwargs['num']
        self.indicators_map = {}
        self.month = None
        self.prediction_interval = Time.Multiply(Extensions.ToTimeSpan(Resolution.Daily), 5) ## Arbitrary
        self.spy = kwargs['spy']
        self.spy_ma = SimpleMovingAverage(150)

    def update_spy(self, data):
        if not data.ContainsKey(self.spy) or data[self.spy] is None:
            return
        self.spy_ma.Update(data[self.spy].EndTime, data[self.spy].Close)


    def Update(self, algorithm, data):
        symbols = []
        for symbol in self.symbols:
            if symbol not in self.indicators_map:
                self.indicators_map[symbol] = SharpeIndicators(look_back=self.look_back)
            if not data.ContainsKey(symbol) or data[symbol] is None:
                continue
            self.indicators_map[symbol].update(data[symbol])
            if self.indicators_map[symbol].ready:
                symbols.append(symbol)
        if algorithm.Time.month == self.month:
            return []
        self.month = algorithm.Time.month
        if not symbols:
            return []
        highest_sharpe = sorted(
            symbols, 
            key=lambda symbol: self.indicators_map[symbol].sharpe.Current.Value, 
            reverse=True,
        )[:self.num]
        # risk management
        if data.ContainsKey(self.spy) and data[self.spy] is not None:
            if data[self.spy].Close < self.spy_ma.Current.Value:
                return [Insight(symbol, self.prediction_interval, InsightType.Price, InsightDirection.Flat, None, None) for symbol in self.symbols]
        return [self.get_insight(algorithm, data, symbol) for symbol in highest_sharpe]
            

class BuyTheWorstMeanReversion(BaseAlpha):
    """
    A U.S. sector rotation Mean Reversion Strategy
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.symbols = kwargs['symbols']
        self.indicators_map = {}
        self.month = None
        self.prediction_interval = Time.Multiply(Extensions.ToTimeSpan(Resolution.Daily), 5) ## Arbitrary

    def Update(self, algorithm, data):
        symbols = []
        for symbol in self.symbols:
            if symbol not in self.indicators_map:
                self.indicators_map[symbol] = RocIndicators()
            if not data.ContainsKey(symbol) or data[symbol] is None:
                continue
            self.indicators_map[symbol].update(data[symbol])
            if self.indicators_map[symbol].ready:
                symbols.append(symbol)
        if algorithm.Time.month == self.month:
            return []
        self.month = algorithm.Time.month
        if not symbols:
            return []
        worst_performer = sorted(
            symbols, 
            key=lambda symbol: self.indicators_map[symbol].monthly_performance, 
            reverse=True,
        )[0]
        return [self.get_insight(algorithm, data, worst_performer)]


class MonthlySectorRotation(QCAlgorithm):
    def Initialize(self):
        self.SetStartDate(2002, 1, 1)
        self.SetEndDate(2022, 11, 1)
        self.SetCash(10000)
        self.SetWarmUp(datetime.timedelta(200), Resolution.Daily)
        self.UniverseSettings.Resolution = Resolution.Daily
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
        symbols = [self.AddEquity(ticker, Resolution.Daily).Symbol for ticker in tickers]
        spy = self.AddEquity(hedge_tickers[0], Resolution.Daily).Symbol
        self.SetAlpha(
            CompositeAlphaModel(
                MonthlyRotation(symbols=symbols, look_back=198, num=1, spy=spy, equity_risk_pc=self.equity_risk_pc),
                MonthlyRotation(symbols=symbols, look_back=7, num=1, spy=spy, equity_risk_pc=self.equity_risk_pc),
                BuyTheWorstMeanReversion(symbols=symbols, equity_risk_pc=self.equity_risk_pc),
            )
        )
        self.SetPortfolioConstruction(ConfidenceWeightedPortfolioConstructionModel(self.DateRules.MonthStart()))
        self.SetExecution(ImmediateExecutionModel())
        self.SetRiskManagement(NullRiskManagementModel())
