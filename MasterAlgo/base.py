from AlgorithmImports import Resolution

class BaseStrategy:
    def __init__(self, equity_risk_pc = 0.01, **kwargs) -> None:
        self.equity_risk_pc = equity_risk_pc

    def calculate_position_size(self, algorithm, symbol):
        atr = algorithm.symbols[symbol].atr.Current.Value
        return round((algorithm.Portfolio.TotalPortfolioValue * self.equity_risk_pc) / atr)
    
    def rebalance_due(self, algorithm):
        return algorithm.resolution == Resolution.Daily
    
    def handle_on_data(self, algorithm, data):
        raise NotImplementedError()
    
    def OnData(self, algorithm, data):
        if not self.rebalance_due(algorithm):
            return
        self.handle_on_data(algorithm, data)

    def get_indicator_configs(self):
        return []

    def get_manual_indicator_configs(self):
        return [indicator for indicator in self.get_indicator_configs() if indicator.get('manual')]
    
    def handle_manual_indicators(self, algorithm, data):
        manual_indicators = self.get_manual_indicator_configs()
        if manual_indicators:
            raise NotImplementedError("This class contains manual indicators but doesn't warm them up")