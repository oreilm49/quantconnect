class ReversalDayIndicator:
    def __init__(self, window):
        self.window = window

    def reversal_day(self):
        """
        Checks if the most recent day in the window is a Reversal Day (RD).
        A RD top (short signal) is when the market makes a new high but closes below the prior day's close and the current day's open.
        A RD bottom (long signal) is when the market makes a new low but closes above the prior day's close and the current day's open.
        Returns -1 for a short signal, 1 for a long signal, and 0 for no signal.
        """
        yesterday = self.window[1]
        today = self.window[0]

        if today.high > yesterday.high and today.close < min(yesterday.close, today.open):
            return -1  # Short signal

        if today.low < yesterday.low and today.close > max(yesterday.close, today.open):
            return 1  # Long signal

        return 0  # No signal

    def key_reversal_day(self):
        """
        Checks if the most recent day in the window is a Key Reversal Day (KRD).
        A KRD (short signal) is when the market opens below the prior day's close, makes a new high, but closes below the prior day's close and the current day's open.
        Returns -1 for a short signal and 0 for no signal or long signal not defined for KRD.
        """
        yesterday = self.window[1]
        today = self.window[0]

        if today.open < yesterday.close and today.high > yesterday.high and today.close < min(yesterday.close, today.open):
            return -1  # Short signal

        return 0  # No signal or long signal not defined for KRD

    def outside_reversal_day(self):
        """
        Checks if the most recent day in the window is an Outside Reversal Day (OSRD).
        An OSRD top (short signal) is when the market makes a new high and low, but closes below the prior day's close and the current day's open.
        An OSRD bottom (long signal) is when the market makes a new high and low, but closes above the prior day's close and the current day's open.
        Returns -1 for a short signal, 1 for a long signal, and 0 for no signal.
        """
        yesterday = self.window[1]
        today = self.window[0]

        if (today.high > yesterday.high and today.low < yesterday.low and
                today.close < min(yesterday.close, today.open)):
            return -1  # Short signal

        if (today.high > yesterday.high and today.low < yesterday.low and
                today.close > max(yesterday.close, today.open)):
            return 1  # Long signal

        return 0  # No signal

    def outside_key_reversal_day(self):
        """
        Checks if the most recent day in the window is an Outside Key Reversal Day (OSKRD).
        An OSKRD (short signal) is when the market opens below the prior day's close, makes a new high and low, but closes below the prior day's close and the current day's open.
        Returns -1 for a short signal and 0 for no signal or long signal not defined for OKRD.
        """
        yesterday = self.window[1]
        today = self.window[0]

        if (today.open < yesterday.close and
                today.high > yesterday.high and
                today.low < yesterday.low and
                today.close < min(yesterday.close, today.open)):
            return -1  # Short signal

        return 0  # No signal or long signal not defined for OKRD
