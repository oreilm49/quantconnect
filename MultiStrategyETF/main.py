from AlgorithmImports import *
import datetime
from typing import Dict, List, Tuple


SYMBOLS = 'symbols'
POSITIONS = 'positions'
REBALANCED_DATE = 'rebalanced_date'


class SymbolIndicators:
    def __init__(self) -> None:
        self.sharpe_long = SharpeRatio(198)
        self.sharpe_short = SharpeRatio(7)
        self.atr = AverageTrueRange(21)
        self.roc_10 = RateOfChange(10)
        self.roc_20 = RateOfChange(20)
        
    def update(self, trade_bar):
        self.sharpe_long.Update(trade_bar.EndTime, trade_bar.High)
        self.atr.Update(trade_bar)
    
    @property
    def ready(self):
        return all((
            self.sharpe_long.IsReady,
            self.atr.IsReady,
        ))
    
    @property
    def monthly_performance(self) -> float:
        return self.roc_10.Current.Value + (-2 * self.roc_20.Current.Value)


class BaseAlpha(object):
    EQUITY_RISK_PC = 0.01

    def __init__(self, algorithm: QCAlgorithm, indicators: Dict[Symbol, SymbolIndicators], bars, symbols: List[Symbol]) -> None:
        self.algorithm = algorithm
        self.indicators = indicators
        self.bars = bars
        self.symbols = symbols
    
    def get_signals(self) -> int:
        raise NotImplementedError()
    
    def calculate_position_size(self, atr):
        return round((self.algorithm.Portfolio.TotalPortfolioValue * self.EQUITY_RISK_PC) / atr)
    
    @property
    def positions(self) -> Dict[Symbol, int]:
        return self.algorithm.alpha_map[self.__class__][POSITIONS]
    
    @property
    def rebalanced_date(self) -> Optional[datetime.datetime]:
        return self.algorithm.alpha_map[self.__class__][REBALANCED_DATE]

    def rebalancing_due(self) -> bool:
        """Only rebalance if nothing has changed in previous 30 days"""
        rebalanced: Optional[datetime.datetime] = self.rebalanced_date
        if not rebalanced:
            return True
        return (datetime.datetime.now() - rebalanced) > datetime.timedelta(days=30)
    

class MonthlyRotation(BaseAlpha):
    """
    A U.S. sector rotation Momentum Strategy with a long lookback period
    """
    indicator_key = 'sharpe_long'

    def get_signals(self) -> List[Tuple[Symbol, int]]:
        signals = []
        if not self.rebalancing_due:
            return []   
        highest_sharpe = sorted(
            self.symbols, 
            key=lambda symbol: getattr(self.indicators[symbol], self.indicator_key), 
            reverse=True,
        )[:3]
        for symbol in self.symbols:
            if symbol not in self.positions:
                if symbol in highest_sharpe:
                    signals.append((symbol, self.calculate_position_size(self.indicators[symbol].atr.Current.Value)))
            elif symbol not in highest_sharpe:
                existing_position_size = self.positions[symbol]
                signals.append((symbol, -1 * existing_position_size))
        return signals
    

class ShortMonthlyRotation(MonthlyRotation):
    indicator_key = 'sharpe_short'


class BuyTheWorstMeanReversion(BaseAlpha):

    def get_signals(self) -> List[Tuple[Symbol, int]]:
        signals = []
        if not self.rebalancing_due or not self.symbols:
            return []   
        worst_performer = sorted(
            self.symbols, 
            key=lambda symbol: self.indicators[symbol].monthly_performance, 
            reverse=True,
        )[0]
        for symbol in self.symbols:
            if symbol not in self.positions:
                if symbol == worst_performer:
                    signals.append((symbol, self.calculate_position_size(self.indicators[symbol].atr.Current.Value)))
            elif symbol != worst_performer:
                existing_position_size = self.positions[symbol]
                signals.append((symbol, -1 * existing_position_size))
        return signals


class MultiStrategyETF(QCAlgorithm):
    def Initialize(self):
        self.SetStartDate(2002, 1, 1)
        self.SetEndDate(2022, 11, 1)
        self.SetCash(10000)
        self.SetWarmUp(timedelta(200), Resolution.Daily)
        self.UniverseSettings.Resolution = Resolution.Daily
        self.SetBrokerageModel(BrokerageName.InteractiveBrokersBrokerage)
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
        self.alpha_map = {
            MonthlyRotation: {
                SYMBOLS: tickers,
                POSITIONS: {},
                REBALANCED_DATE: None,
            },
            ShortMonthlyRotation: {
                SYMBOLS: tickers,
                POSITIONS: {},
                REBALANCED_DATE: None,
            },
            BuyTheWorstMeanReversion: {
                SYMBOLS: tickers,
                POSITIONS: {},
                REBALANCED_DATE: None,
            },
        }
        for ticker in tickers:
            self.AddEquity(ticker, Resolution.Daily)

    def update_indicators(self, data) -> Iterator[Symbol]:
        for symbol in self.ActiveSecurities.Keys:
            if not data.Bars.ContainsKey(symbol):
                continue
            if symbol not in self.symbol_map:
                self.symbol_map[symbol] = SymbolIndicators()
            self.symbol_map[symbol].update(data.Bars[symbol])
            if not self.symbol_map[symbol].ready:
                continue
            yield symbol

    def OnData(self, data):
        symbols = list(self.update_indicators(data))
        if not symbols:
            return
        for Alpha in self.alpha_map.keys():
            allowed_symbols = [symbol for symbol in symbols if str(symbol.Value) in self.alpha_map[Alpha][SYMBOLS]]
            for signal in Alpha(self, self.symbol_map, data.Bars, allowed_symbols).get_signals():
                if signal:
                    symbol, size = signal
                    if size > 0:
                        value = size * self.ActiveSecurities[symbol].Price
                        if value < self.Portfolio.Cash:
                            self.MarketOrder(symbol, size)
                    else:
                        self.MarketOrder(symbol, size)
