from collections import namedtuple
from AlgorithmImports import *
from typing import Dict, List, Tuple, Type


class RocIndicators:
    def __init__(self) -> None:
        self.roc_10 = RateOfChangePercent(10)
        self.roc_20 = RateOfChangePercent(20)
        
    def update(self, trade_bar):
        self.roc_10.Update(trade_bar.EndTime, trade_bar.Close)
        self.roc_20.Update(trade_bar.EndTime, trade_bar.Close)
    
    @property
    def ready(self):
        return all((
            self.roc_10.IsReady,
            self.roc_20.IsReady,
        ))
    
    @property
    def monthly_performance(self) -> float:
        return self.roc_10.Current.Value + (-2 * self.roc_20.Current.Value)
    

class MonthlyRotation(AlphaModel):
    """
    A U.S. sector rotation Momentum Strategy with a long lookback period
    """
    def __init__(self, *args, **kwargs):
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
                self.indicators_map[symbol] = SharpeRatio(self.look_back)
            if not data.ContainsKey(symbol) or data[symbol] is None:
                continue
            self.indicators_map[symbol].Update(data[symbol].EndTime, data[symbol].Close)
            if self.indicators_map[symbol].IsReady:
                symbols.append(symbol)
        if algorithm.Time.month == self.month:
            return []
        self.month = algorithm.Time.month
        if not symbols:
            return []
        highest_sharpe = sorted(
            symbols, 
            key=lambda symbol: self.indicators_map[symbol].Current.Value, 
            reverse=True,
        )[:self.num]
        # risk management
        if data.ContainsKey(self.spy) and data[self.spy] is not None:
            if data[self.spy].Close < self.spy_ma.Current.Value:
                return [Insight(symbol, self.prediction_interval, InsightType.Price, InsightDirection.Flat, None, None) for symbol in algorithm.ActiveSecurities.Keys]
        return [Insight(symbol, self.prediction_interval, InsightType.Price, InsightDirection.Up, None, None) for symbol in highest_sharpe]
            

class BuyTheWorstMeanReversion(AlphaModel):
    """
    A U.S. sector rotation Mean Reversion Strategy
    """
    def __init__(self, *args, **kwargs):
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
        return [Insight(worst_performer, self.prediction_interval, InsightType.Price, InsightDirection.Up, None, None)]
    

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
        self.SetWarmUp(timedelta(200), Resolution.Daily)
        self.UniverseSettings.Resolution = Resolution.Daily
        self.SetBrokerageModel(BrokerageName.InteractiveBrokersBrokerage)
        self.Settings.RebalancePortfolioOnInsightChanges = False
        self.Settings.RebalancePortfolioOnSecurityChanges = False
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
                MonthlyRotation(symbols=symbols, look_back=198, num=1, spy=spy),
                MonthlyRotation(symbols=symbols, look_back=7, num=1, spy=spy),
                BuyTheWorstMeanReversion(symbols=symbols),
                Hedge(
                    spy=self.AddEquity(hedge_tickers[0], Resolution.Daily).Symbol,
                    hedge=self.AddEquity(hedge_tickers[1], Resolution.Daily).Symbol,
                )
            )
        )
        self.SetPortfolioConstruction(EqualWeightingPortfolioConstructionModel(self.DateRules.MonthStart()))
        self.SetExecution(ImmediateExecutionModel())
        self.SetRiskManagement(NullRiskManagementModel())
