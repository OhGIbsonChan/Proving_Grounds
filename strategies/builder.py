# strategies/builder.py
import pandas_ta_classic as ta
from .base import BaseStrategy
from pydantic import BaseModel
from typing import List, Literal, Optional, Union

# --- 1. THE RECIPE "SCHEMA" ---
class IndicatorConfig(BaseModel):
    name: str           # e.g., "RSI", "SMA", "Close"
    params: dict = {}   # e.g., {"length": 14}
    
class Rule(BaseModel):
    indicator_a: IndicatorConfig
    operator: Literal[">", "<", "==", "crosses_above", "crosses_below"]
    # We can compare against a number OR another indicator
    indicator_b: Union[IndicatorConfig, float] 

class StrategyRecipe(BaseModel):
    name: str
    description: str = "Custom Strategy"
    entry_rules: List[Rule]
    exit_rules: List[Rule]
    stop_loss_atr: float = 2.0
    take_profit_atr: float = 3.0

# --- 2. THE UNIVERSAL STRATEGY ---
class UniversalStrategy(BaseStrategy):
    """
    The Chameleon. It becomes whatever strategy you tell it to be.
    """
    # This will be injected by the Dashboard
    recipe: StrategyRecipe = None 

    def init(self):
        if not self.recipe: return
        
        # A. PRE-CALCULATE INDICATORS
        # We store them in a dictionary: self.inds['RSI_14'] = ...
        self.inds = {}
        
        # Helper to register an indicator from config
        def register_ind(cfg: IndicatorConfig):
            if isinstance(cfg, float): return # It's just a number
            
            key = self._get_key(cfg)
            if key in self.inds or cfg.name == "Close": return

            # DYNAMIC DISPATCH (The "Factory")
            if cfg.name == "RSI":
                self.inds[key] = self.I(ta.rsi, self.data.Close.s, length=cfg.params.get('length', 14))
            elif cfg.name == "SMA":
                self.inds[key] = self.I(ta.sma, self.data.Close.s, length=cfg.params.get('length', 20))
            elif cfg.name == "EMA":
                self.inds[key] = self.I(ta.ema, self.data.Close.s, length=cfg.params.get('length', 20))
            elif cfg.name == "ATR":
                self.inds[key] = self.I(ta.atr, self.data.High.s, self.data.Low.s, self.data.Close.s, length=14)

        # Scan all rules and register necessary indicators
        all_rules = self.recipe.entry_rules + self.recipe.exit_rules
        for rule in all_rules:
            register_ind(rule.indicator_a)
            if isinstance(rule.indicator_b, IndicatorConfig):
                register_ind(rule.indicator_b)

        # Always calc ATR for stops
        self.atr = self.I(ta.atr, self.data.High.s, self.data.Low.s, self.data.Close.s, length=14)

    def next(self):
        if not self.recipe: return
        
        price = self.data.Close[-1]
        
        # --- CHECK ENTRY RULES (ALL MUST BE TRUE) ---
        entry_signal = True
        if not self.recipe.entry_rules: entry_signal = False

        for rule in self.recipe.entry_rules:
            if not self.check_rule(rule):
                entry_signal = False
                break
        
        # --- EXECUTE ---
        if not self.position and entry_signal:
            atr_val = self.atr[-1]
            sl = price - (atr_val * self.recipe.stop_loss_atr)
            tp = price + (atr_val * self.recipe.take_profit_atr)
            
            # Use fixed size from your config
            import config
            self.buy(sl=sl, tp=tp, size=config.FIXED_SIZE)

    def check_rule(self, rule: Rule):
        # 1. Get Value A
        val_a = self.get_val(rule.indicator_a)
        
        # 2. Get Value B
        if isinstance(rule.indicator_b, float):
            val_b = rule.indicator_b
        else:
            val_b = self.get_val(rule.indicator_b)
            
        # 3. Compare
        if rule.operator == ">": return val_a > val_b
        if rule.operator == "<": return val_a < val_b
        if rule.operator == "==": return val_a == val_b
        # (Cross logic would require looking at previous candle [-2], simple for now)
        return False

    def get_val(self, cfg: IndicatorConfig):
        if cfg.name == "Close": return self.data.Close[-1]
        key = self._get_key(cfg)
        return self.inds[key][-1]

    def _get_key(self, cfg):
        return f"{cfg.name}_{cfg.params}"