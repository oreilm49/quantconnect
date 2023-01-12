import datetime
from AlgorithmImports import Resolution, AverageTrueRange, SimpleMovingAverage, MoneyFlowIndex,\
    BrokerageName, QCAlgorithm, QC500UniverseSelectionModel, ImmediateExecutionModel, Field
from turtle_trading import TurtleTrading


class MasterAlgo(QCAlgorithm):
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
        self.strategies = (
            # initialize strategy classes here
            TurtleTrading(high_lookback=40),
        )


    def OnSecuritiesChanged(self, changes):
        for added in changes.AddedSecurities:
            self.symbols[added.Symbol] = SymbolData(
                self, added, self.resolution,
            )

        for removed in changes.RemovedSecurities:
            data = self.symbols.pop(removed.Symbol, None)
            if data is not None:
                self.SubscriptionManager.RemoveConsolidator(removed.Symbol, data.Consolidator)

    def OnData(self, data):
        for strategy in self.strategies:
            strategy.OnData(self, data)


class SymbolData:
    def __init__(self, algorithm, security, resolution):
        self.security = security
        self.atr = AverageTrueRange(atr_lookback)
        self.sma = SimpleMovingAverage(sma_lookback)
        self.Consolidator = algorithm.ResolveConsolidator(security.Symbol, resolution)
        self.positions = {}
        for indicator in (self.mfi, self.atr, self.sma):
            algorithm.RegisterIndicator(security.Symbol, indicator, self.Consolidator)
            algorithm.WarmUpIndicator(security.Symbol, indicator, resolution)

    def add_position(self, strategy_name, size, direction):
        self.positions[strategy_name] = {
            "size": size,
            "direction": direction,
            "confirmed": False
        }

    def confirm_position(self, size, direction):
        strategy_name, _ = [(strategy_name, position) for strategy_name, position in self.positions.items()\
                  if position[size] == size and position[direction] == direction][0]
        self.positions[strategy_name]["confirmed"] = True
    
    def liquidate_position(self, strategy_name):
        del self.positions[strategy_name]

    def get_position(self, strategy_name):
        return self.positions[strategy_name]
    
