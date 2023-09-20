class ReversalDayIndicator:
    def __init__(self, window):
        self.window = window
        self.stop_loss_wiggle_pc = 0.02
        self.today = self.window[0]
        self.yesterday = self.window[1]
        self.short_stop_loss = self.today.High * (1 + self.stop_loss_wiggle_pc)
        self.long_stop_loss = self.today.Low * (1 - self.stop_loss_wiggle_pc)

    def get_signal(self):
        for indicator, stop_loss in [
            self.reversal_day,
            self.key_reversal_day,
            self.outside_reversal_day,
            self.outside_key_reversal_day,
        ]:
            if indicator is not 0:
                return indicator, stop_loss
        return 0, None

    @property
    def reversal_day(self):
        """
        Checks if the most recent day in the window is a Reversal Day (RD).
        A RD top (short signal) is when the market makes a new high but closes below the prior day's close and the current day's open.
        A RD bottom (long signal) is when the market makes a new low but closes above the prior day's close and the current day's open.
        Returns -1 for a short signal, 1 for a long signal, and 0 for no signal.
        """
        if self.yesterday.Volume > self.today.Volume:
            return 0, None  # No signal

        if self.today.High > self.yesterday.High and self.today.Close < min(self.yesterday.Close, self.today.Open):
            return -1, self.short_stop_loss  # Short signal and stop loss

        if self.today.Low < self.yesterday.Low and self.today.Close > max(self.yesterday.Close, self.today.Open):
            return 1, self.long_stop_loss  # Long signal and stop loss

        return 0, None  # No signal

    @property
    def key_reversal_day(self):
        """
        Checks if the most recent day in the window is a Key Reversal Day (KRD).
        A KRD (short signal) is when the market opens below the prior day's close, makes a new high, but closes below the prior day's close and the current day's open.
        A KRD (long signal) is when the market opens above the prior day's close, makes a new low, but closes above the prior day's close and the current day's open.
        Returns -1 for a short signal, 1 for a long signal, and 0 for no signal.
        """
        
        if self.yesterday.Volume > self.today.Volume:
            return 0, None  # No signal

        if self.today.Open < self.yesterday.Close and self.today.High > self.yesterday.High and self.today.Close < min(self.yesterday.Close, self.today.Open):
            return -1, self.short_stop_loss  # Short signal and stop loss

        if self.today.Open > self.yesterday.Close and self.today.Low < self.yesterday.Low and self.today.Close > max(self.yesterday.Close, self.today.Open):
            return 1, self.long_stop_loss  # Long signal and stop loss

        return 0, None  # No signal


    @property
    def outside_reversal_day(self):
        """
        Checks if the most recent day in the window is an Outside Reversal Day (OSRD).
        An OSRD top (short signal) is when the market makes a new high and low, but closes below the prior day's close and the current day's open.
        An OSRD bottom (long signal) is when the market makes a new high and low, but closes above the prior day's close and the current day's open.
        Returns -1 for a short signal, 1 for a long signal, and 0 for no signal.
        """
        if self.yesterday.Volume > self.today.Volume:
            return 0, None  # No signal

        if (self.today.High > self.yesterday.High and self.today.Low < self.yesterday.Low and
                self.today.Close < min(self.yesterday.Close, self.today.Open)):
            return -1, self.short_stop_loss  # Short signal and stop loss

        if (self.today.High > self.yesterday.High and self.today.Low < self.yesterday.Low and
                self.today.Close > max(self.yesterday.Close, self.today.Open)):
            return 1, self.long_stop_loss  # Long signal and stop loss

        return 0, None  # No signal

    @property
    def outside_key_reversal_day(self):
        """
        Checks if the most recent day in the window is an Outside Key Reversal Day (OSKRD).
        An OSKRD (short signal) is when the market opens below the prior day's close, makes a new high and low, but closes below the prior day's close and the current day's open.
        An OSKRD (long signal) is when the market opens above the prior day's close, makes a new high and low, but closes above the prior day's close and the current day's open.
        Returns -1 for a short signal, 1 for a long signal, and 0 for no signal.
        """
        if self.yesterday.Volume > self.today.Volume:
            return 0, None  # No signal

        if (self.today.Open < self.yesterday.Close and
                self.today.High > self.yesterday.High and
                self.today.Low < self.yesterday.Low and
                self.today.Close < min(self.yesterday.Close, self.today.Open)):
            return -1, self.short_stop_loss  # Short signal and stop loss

        if (self.today.Open > self.yesterday.Close and
                self.today.High > self.yesterday.High and
                self.today.Low < self.yesterday.Low and
                self.today.Close > max(self.yesterday.Close, self.today.Open)):
            return 1, self.long_stop_loss  # Long signal and stop loss

        return 0, None  # No signal