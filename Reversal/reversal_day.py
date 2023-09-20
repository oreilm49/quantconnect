class ReversalDayIndicator:
    def __init__(self, window):
        self.window = window
        self.signal = self.get_signal()
    
    def get_signal(self):
        for indicator, stop_loss in [
            self.reversal_day,
            self.key_reversal_day,
            self.outside_reversal_day,
            self.outside_key_reversal_day,
        ]:
            if indicator is not 0:
                return indicator, stop_loss

    @property
    def reversal_day(self):
        """
        Checks if the most recent day in the window is a Reversal Day (RD).
        A RD top (short signal) is when the market makes a new high but closes below the prior day's close and the current day's open.
        A RD bottom (long signal) is when the market makes a new low but closes above the prior day's close and the current day's open.
        Returns -1 for a short signal, 1 for a long signal, and 0 for no signal.
        """
        yesterday = self.window[1]
        today = self.window[0]

        if today.High > yesterday.High and today.Close < min(yesterday.Close, today.Open):
            return -1, today.High  # Short signal and stop loss

        if today.Low < yesterday.Low and today.Close > max(yesterday.Close, today.Open):
            return 1, today.Low  # Long signal and stop loss

        return 0, None  # No signal

    @property
    def key_reversal_day(self):
        """
        Checks if the most recent day in the window is a Key Reversal Day (KRD).
        A KRD (short signal) is when the market opens below the prior day's close, makes a new high, but closes below the prior day's close and the current day's open.
        Returns -1 for a short signal and 0 for no signal or long signal not defined for KRD.
        """
        yesterday = self.window[1]
        today = self.window[0]

        if today.Open < yesterday.Close and today.High > yesterday.High and today.Close < min(yesterday.Close, today.Open):
            return -1, today.High  # Short signal and stop loss

        return 0, None  # No signal or long signal not defined for KRD

    @property
    def outside_reversal_day(self):
        """
        Checks if the most recent day in the window is an Outside Reversal Day (OSRD).
        An OSRD top (short signal) is when the market makes a new high and low, but closes below the prior day's close and the current day's open.
        An OSRD bottom (long signal) is when the market makes a new high and low, but closes above the prior day's close and the current day's open.
        Returns -1 for a short signal, 1 for a long signal, and 0 for no signal.
        """
        yesterday = self.window[1]
        today = self.window[0]

        if (today.High > yesterday.High and today.Low < yesterday.Low and
                today.Close < min(yesterday.Close, today.Open)):
            return -1, today.High  # Short signal and stop loss

        if (today.High > yesterday.High and today.Low < yesterday.Low and
                today.Close > max(yesterday.Close, today.Open)):
            return 1, today.Low  # Long signal and stop loss

        return 0, None  # No signal

    @property
    def outside_key_reversal_day(self):
        """
        Checks if the most recent day in the window is an Outside Key Reversal Day (OSKRD).
        An OSKRD (short signal) is when the market opens below the prior day's close, makes a new high and low, but closes below the prior day's close and the current day's open.
        Returns -1 for a short signal and 0 for no signal or long signal not defined for OKRD.
        """
        yesterday = self.window[1]
        today = self.window[0]

        if (today.Open < yesterday.Close and
                today.High > yesterday.High and
                today.Low < yesterday.Low and
                today.Close < min(yesterday.Close, today.Open)):
            return -1, today.High  # Short signal and stop loss

        return 0, None  # No signal or long signal not defined for OKRD

