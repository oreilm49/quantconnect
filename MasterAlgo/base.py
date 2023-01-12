class BaseStrategy:
    def calculate_position_size(self, algorithm, symbol):
        atr = algorithm.symbols[symbol].atr.Current.Value
        return round((algorithm.Portfolio.TotalPortfolioValue * algorithm.EQUITY_RISK_PC) / atr)
    
    def rebalance_due(self):
        raise NotImplementedError()
    
    def handle_on_data(self, algorithm, data):
        raise NotImplementedError()
    
    def OnData(self, algorithm, data):
        if not self.rebalance_due:
            return
        self.handle_on_data(algorithm, data)