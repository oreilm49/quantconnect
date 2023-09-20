from AlgorithmImports import QCAlgorithm, Resolution, BrokerageName
from indicators import SymbolIndicators


class Reversal(QCAlgorithm):
    def Initialize(self):
        self.SetCash(10000)
        self.UniverseSettings.Resolution = Resolution.Daily
        self.SetBrokerageModel(BrokerageName.InteractiveBrokersBrokerage)
        self.EQUITY_RISK_PC = 0.0075
        self.symbol_map = {}
        self.SL_RISK_PC = -0.05
        self.TP_TARGET = 0.20
        self.SetStartDate(2021, 1, 1)
        self.SetEndDate(2022, 12, 31)
        self.symbols = ["AAPL"]
        self.symbol_map = {}
        for symbol in self.symbols:
            self.AddEquity(symbol, Resolution.Daily)
    
    def OnData(self, data):
        for symbol in self.ActiveSecurities.Keys:
            if symbol.Value not in self.symbols:
                continue
            if not data.Bars.ContainsKey(symbol):
                continue
            if symbol not in self.symbol_map:
                self.symbol_map[symbol] = {
                    'indicators': SymbolIndicators(self, symbol),
                }
            else:
                self.symbol_map[symbol]['indicators'].update(data.Bars[symbol])
            indicators = self.symbol_map[symbol]['indicators']
            if not indicators.ready:
                continue
            reversal, stop_loss = indicators.reversal.get_signal()
            if reversal == 0:
                continue
            elif reversal < 0:
                self.Liquidate(symbol)
                if 'sl' in self.symbol_map[symbol]:
                    self.symbol_map[symbol]['sl'].Cancel()
            elif reversal > 0 and not self.ActiveSecurities[symbol].Invested:
                self.buy(symbol, stop_loss=stop_loss)
    
    def buy(self, symbol, order_tag=None, stop_loss=None):
        position_size = self.get_position_size(symbol)
        position_value = position_size * self.ActiveSecurities[symbol].Price
        if position_value < self.Portfolio.Cash:
            self.MarketOrder(symbol, position_size, tag=order_tag)
            if stop_loss:
                self.symbol_map[symbol]['sl'] = self.StopMarketOrder(symbol, -position_size, stop_loss) 

    def get_position_size(self, symbol):
        """
        Gets the lowest risk position size
        volatility_size = ($total equity * portfolio risk %) / ATR(21)
        risk_size = ($total equity * portfolio risk %) / $value of risk on trade
        """
        volatility_size = (self.Portfolio.TotalPortfolioValue * self.EQUITY_RISK_PC) / self.symbol_map[symbol]['indicators'].atr.Current.Value
        risk_size = (self.Portfolio.TotalPortfolioValue * self.EQUITY_RISK_PC) / (self.ActiveSecurities[symbol].Price * (self.SL_RISK_PC * -1))
        return round(min(volatility_size, risk_size))

