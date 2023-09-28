import datetime
from AlgorithmImports import SimpleMovingAverage, AverageTrueRange, RollingWindow, TradeBar,\
    Resolution, Maximum
from datetime import timedelta
import pandas as pd
import numpy as np


class SymbolIndicators:
    def __init__(self, algorithm, symbol) -> None:
        self.algorithm = algorithm
        self.sma = SimpleMovingAverage(50)
        self.sma_volume = SimpleMovingAverage(50)
        self.sma_200 = SimpleMovingAverage(200)
        self.atr = AverageTrueRange(21)
        self.trade_bar_window = RollingWindow[TradeBar](200)
        self.max_price = Maximum(200)
        self.sma_window = RollingWindow[float](2)
        self.breakout_window = RollingWindow[float](1)

        history = algorithm.History(symbol, 200, Resolution.Daily)
        for data in history.itertuples():
            trade_bar = TradeBar(data.Index[1], data.Index[0], data.open, data.high, data.low, data.close, data.volume, timedelta(1))
            self.update(trade_bar)
        
    def update(self, trade_bar):
        self.sma.Update(trade_bar.EndTime, trade_bar.Close)
        self.sma_volume.Update(trade_bar.EndTime, trade_bar.Volume)
        self.sma_200.Update(trade_bar.EndTime, trade_bar.Close)
        self.atr.Update(trade_bar)
        self.trade_bar_window.Add(trade_bar)
        self.max_price.Update(trade_bar.EndTime, trade_bar.High)
        self.sma_window.Add(self.sma.Current.Value)
        if self.breakout_ready:
            level = self.is_breakout
            if level:
                self.breakout_window.Add(level)
    
    @property
    def ready(self):
        return all((
            self.sma.IsReady,
            self.sma_volume.IsReady,
            self.sma_200.IsReady,
            self.atr.IsReady,
            self.trade_bar_window.IsReady,
            self.max_price.IsReady,
            self.sma_window.IsReady,
        ))
        
    @property
    def breakout_ready(self):
        return all((
            self.sma_volume.IsReady,
            self.trade_bar_window.IsReady,
        ))

    
    def atrp(self, close):
        return (self.atr.Current.Value / close) * 100
    
    @property
    def uptrending(self):
        """
        The stock is deemed to be uptrending if the 50 SMA is above 200 SMA
        and the latest close is above the 200 SMA.
        
        :return: True if uptrending.
        """
        trade_bar_lts = self.trade_bar_window[0]
        return self.sma.Current.Value > self.sma_200.Current.Value and trade_bar_lts.Close > self.sma_200.Current.Value

    @property
    def high_7_weeks_ago(self) -> bool:
        return self.max_price.PeriodsSinceMaximum > 5 * 7
    
    @property
    def weekly_data(self):
        df = self.algorithm.PandasConverter.GetDataFrame[TradeBar](list(self.trade_bar_window)[::-1]).reset_index()
        df.index = df.time
        df = df.resample('W-Fri')
        df = df.apply({
            'open':'first',
            'high':'max',
            'low':'min',
            'close':'last',
            'volume':'sum'
        })
        return df
    
    def get_resistance_levels(self, df, range_filter: float = 0.005, peak_range: int = 3) -> list:
        """
        Finds major resistance levels for data in self.trade_bar_window.
        Resamples daily data to weekly to find weekly resistance levels.

        :param range_filter: Decides if two prices are part of the same resistance level.
        :param peak_range: Number of candles to check either side of peak candle.
        :return: set of price resistance levels.
        """
        peaks_by_time = {}
        for i in range(peak_range, len(df) - peak_range):
            greater_than_prior_prices = df.iloc[i].high > df.iloc[i - peak_range].high
            greater_than_future_prices = df.iloc[i].high > df.iloc[i + peak_range].high
            if greater_than_prior_prices and greater_than_future_prices:
                peaks_by_time[df.iloc[i].high] = df.iloc[i].time
        del df
        levels = []
        peaks = sorted(peaks_by_time.values())
        for i, curr_peak in enumerate(peaks):
            level = None
            if i == 0:
                continue
            prev_peak_upper_range = peaks[i - 1] + (peaks[i - 1] * range_filter)
            if curr_peak < prev_peak_upper_range:
                level = curr_peak
            if level and levels:
                prev_level_upper_range = levels[-1] + (levels[-1] * range_filter)
                if level < prev_level_upper_range:
                    levels.pop()
            if level:
                levels.append(level)
        return levels, peaks_by_time
    
    @property
    def is_breakout(self):
        """
        Determines if the current candle is a breakout.
        If so, returns the breakout price level.
        """
        trade_bar_lts = self.trade_bar_window[0]
        trade_bar_prev = self.trade_bar_window[1]
        weekly_data = self.weekly_data
        levels, peaks_by_time = self.get_resistance_levels(weekly_data)
        for level in levels:
            if level > trade_bar_lts.High:
                # levels are ordered in ascending order.
                # no point in checking any more.
                break
            # require above average volume
            if not trade_bar_lts.Volume > self.sma_volume.Current.Value \
                and not trade_bar_prev.Volume > self.sma_volume.Current.Value:
                continue
            daily_breakout = trade_bar_lts.Open < level and trade_bar_lts.Close > level
            gap_up_breakout = trade_bar_prev.Close < level and trade_bar_lts.Open > level
            if (daily_breakout or gap_up_breakout) and self.vcp_in_base(weekly_data, peaks_by_time[level]):
                return level
    
    def vcp_in_base(self, df: pd.Dataframe, base_start: datetime.datetime) -> bool:
        df = df.loc[(df['date'] >= base_start)]
        # Identify start of correction periods (new high after low)
        df['new_high'] = df.high > df.high.shift(1)
        df['new_low'] = df.low < df.low.shift(1)
        df['correction_start'] = df.new_low & df.new_high.shift(1)

        # Identify end of correction periods (new low after high)
        df['correction_end'] = df.new_high & df.new_low.shift(1)

        # Forward fill the Open price from the start of the correction
        df.loc[df['correction_start'], 'correction_open'] = df['open']
        df['correction_open'] = df['correction_open'].ffill()

        # Calculate the correction
        df['correction'] = np.where(df['correction_end'], (df['high'] - df['low']) / df['correction_open'], np.nan)

        # Get the list of corrections
        corrections = df.loc[df['correction_end'], 'correction'].tolist()
        # Calculate if more than 60% of corrections are smaller than the prior one
        smaller_corrections = [i < j for i, j in zip(corrections[:-1], corrections[1:])]
        return sum(smaller_corrections) / len(smaller_corrections) > 0.6
