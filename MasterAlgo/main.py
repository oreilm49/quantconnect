import datetime
from AlgorithmImports import Resolution, BrokerageName, QCAlgorithm, QC500UniverseSelectionModel, \
    ImmediateExecutionModel, RollingWindow, OrderEvent, OrderStatus, OrderTicket
from turtle_trading import TurtleTrading


class MyQC500(QC500UniverseSelectionModel):
    """
    Optimized to select the top 250 stocks by dollar volume
    """
    numberOfSymbolsCoarse = 250


class MasterAlgo(QCAlgorithm):
    def Initialize(self):
        self.SetStartDate(2002, 1, 1)
        self.SetCash(100000)
        self.resolution = Resolution.Daily
        self.SetWarmUp(datetime.timedelta(200), self.resolution)
        self.UniverseSettings.Resolution = self.resolution
        self.SetBrokerageModel(BrokerageName.InteractiveBrokersBrokerage)
        self.SetUniverseSelection(MyQC500())
        self.SetExecution(ImmediateExecutionModel())
        self.symbols = {}
        self.EQUITY_RISK_PC = 0.02
        self.strategies = (
            # initialize strategy classes here
            TurtleTrading(high_lookback=40),
        )
        self.indicator_configs = []
        for strategy in self.strategies:
            self.indicator_configs += strategy.get_indicator_configs()


    def OnSecuritiesChanged(self, changes):
        for added in changes.AddedSecurities:
            self.symbols[added.Symbol] = SymbolData(
                self, added, self.resolution, self.indicator_configs
            )

        for removed in changes.RemovedSecurities:
            data = self.symbols.pop(removed.Symbol, None)
            if data is not None:
                self.SubscriptionManager.RemoveConsolidator(
                    removed.Symbol, data.Consolidator
                )
                del data

    def OnData(self, data):
        for strategy in self.strategies:
            strategy.handle_manual_indicators(self, data)
            if self.IsWarmingUp:
                continue
            strategy.OnData(self, data)

    def OnOrderEvent(self, event: OrderEvent) -> None:
        if event.Status == OrderStatus.Filled:
            self.symbols[event.Symbol].confirm_position(event)
        elif event.Status in (OrderStatus.Canceled, OrderStatus.Invalid):
            strategy_name = self.get_strategy_name_for_order_id(event.OrderId)
            self.symbols[event.Symbol].delete_position(strategy_name)

    def buy(self, symbol, position_size, strategy_name):
        self.symbols[symbol].add_position(
            self.MarketOrder(symbol, position_size), 
            strategy_name,
        )

    def liquidate(self, symbol, strategy_name):
        self.Liquidate(symbol)
        self.symbols[symbol].delete_position(strategy_name)


class SymbolData:
    def __init__(self, algorithm, security, resolution, indicator_configs):
        self.security = security
        self.algorithm = algorithm
        self.Consolidator = algorithm.ResolveConsolidator(security.Symbol, resolution)
        # "strategy_name": {"order_id" 1, "created" datetime.datetime()}
        self.positions = {}
        self.indicators = []
        for config in indicator_configs:
            if config['class'] == RollingWindow:
                indicator_class = config['class'][config['window_type']](*config['args'])
            else:
                indicator_class = config['class'](*config['args'])
            setattr(self, config['name'], indicator_class)
            indicator = getattr(self, config['name'])
            self.indicators.append(indicator)
            if config.get('manual'):
                continue
            algorithm.RegisterIndicator(security.Symbol, indicator, self.Consolidator)
            algorithm.WarmUpIndicator(security.Symbol, indicator, resolution)

    def add_position(self, order_ticket: OrderTicket, strategy_name: str):
        self.positions[strategy_name] = {
            "order_id": order_ticket.OrderId,
        }

    def get_strategy_name_for_order_id(self, order_id):
        strategy_name, _ = [(strategy_name, position) for strategy_name, position in self.positions.items()\
                  if position["order_id"] == order_id][0]
        return strategy_name


    def confirm_position(self, event: OrderEvent):
        strategy_name = self.get_strategy_name_for_order_id(event.OrderId)
        self.positions[strategy_name]["created"] = self.algorithm.Time
    
    def delete_position(self, strategy_name):
        del self.positions[strategy_name]

    def get_position(self, strategy_name):
        return self.positions[strategy_name]
    
    def get_position_age(self, strategy_name) -> datetime.timedelta:
        return self.get_position(strategy_name)['created'] - self.algorithm.Time
    
    @property
    def ready(self) -> bool:
        return all([indicator.IsReady for indicator in self.indicators])
    