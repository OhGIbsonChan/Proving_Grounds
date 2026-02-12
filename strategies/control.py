from backtesting import Strategy
from backtesting.lib import crossover
from backtesting.test import SMA
from .base import BaseStrategy

class GoldenCrossControl(BaseStrategy):
    """
    THE CONTROL EXPERIMENT
    Logic: Buy when SMA 50 crosses above SMA 200. Sell when below.
    Expected Result: LOSS or BREAK EVEN (on 1m timeframe).
    If this makes huge money, the engine is broken.
    """
    n1 = 50
    n2 = 200

    def init(self):
        # We use simple Moving Averages
        self.sma1 = self.I(SMA, self.data.Close, self.n1)
        self.sma2 = self.I(SMA, self.data.Close, self.n2)

    def next(self):
        # Buy Logic
        if crossover(self.sma1, self.sma2):
            self.buy()

        # Sell Logic
        elif crossover(self.sma2, self.sma1):
            if self.position:
                self.position.close()