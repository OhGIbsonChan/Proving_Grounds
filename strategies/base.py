# strategies/base.py
from backtesting import Strategy
from pydantic import BaseModel

class BaseStrategy(Strategy):
    """
    The Parent Strategy. 
    It forces every child strategy to have a 'Config' class.
    """
    
    # Every strategy must override this with its own Config class
    Config: type[BaseModel] = None 
    
    def __init__(self, broker, data, params):
        super().__init__(broker, data, params)
        
        # If parameters were passed in (from the UI), validate them
        if self.Config and params:
            # We map the incoming dictionary params to our Pydantic Model
            # This ensures types are correct (int stays int)
            self.cfg = self.Config(**params)
        elif self.Config:
            # Fallback to default values defined in the Config class
            self.cfg = self.Config()
        else:
            self.cfg = None

    def eval_indicator(self, indicator_func, *args, **kwargs):
        """ Helper to wrap indicator calculations """
        return self.I(indicator_func, *args, **kwargs)