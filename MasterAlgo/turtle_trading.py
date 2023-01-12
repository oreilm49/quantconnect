from base import BaseStrategy


class TurtleTrading(BaseStrategy):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.high_lookback = kwargs['high_lookback']

    def handle_on_data(self, algorithm, data):
        securities = [
            symbol for symbol in algorithm.symbols.keys() \
            if algorithm.symbols[symbol].sma.Current.Value < algorithm.ActiveSecurities[symbol].Close \
            and algorithm.symbols[symbol].high.PeriodsSinceMaximum >= self.high_lookback -1 \
            and not algorithm.ActiveSecurities[symbol].Invested
        ]
        securities = sorted(
            securities, 
            key=lambda symbol: algorithm.symbols[symbol].mfi.Current.Value,
            reverse=True,
        )[:10]
        for symbol in securities:
            position_size = algorithm.calculate_position_size(symbol)
            position_value = position_size * algorithm.ActiveSecurities[symbol].Price
            if position_value < algorithm.Portfolio.Cash:
                algorithm.MarketOrder(symbol, position_size)
        self.handle_exit_strategy(algorithm)

    def handle_exit_strategy(self, algorithm):
        for symbol in algorithm.symbols.keys():
            if not algorithm.ActiveSecurities[symbol].Invested:
                continue
            if symbol not in algorithm.symbols:
                algorithm.Liquidate(symbol)
            close = algorithm.ActiveSecurities[symbol].Close
            if close < algorithm.symbols[symbol].low.Current.Value:
                algorithm.Liquidate(symbol)
            if algorithm.Portfolio[symbol].UnrealizedProfitPercent >= 0.20 or \
                algorithm.Portfolio[symbol].UnrealizedProfitPercent <= -0.08 or \
                    close < algorithm.symbols[symbol].sma.Current.Value:
                algorithm.Liquidate(symbol)