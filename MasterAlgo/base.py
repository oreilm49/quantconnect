class BaseStrategy:
    def calculate_position_size(self, algorithm, symbol):
        atr = algorithm.symbols[symbol].atr.Current.Value
        return round((algorithm.Portfolio.TotalPortfolioValue * algorithm.EQUITY_RISK_PC) / atr)
    
    def OnData(self, algorithm, data):
        raise NotImplementedError()