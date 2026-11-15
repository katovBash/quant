"""Fixed mfi experiment rule; frozen source signals are reused."""
from src.research.classic_indicator_grid import signals_for_method
STRATEGY_ID = 'mfi-28-rebound-4h'
TIMEFRAME = '4H'
VARIANT = 'mfi_28_rebound'
PAPER_SYMBOLS = ['FESH', 'NMTP', 'SGZH', 'WUSH']
def signal(bars):
    if not bars:
        return None
    entries, _ = signals_for_method('mfi', VARIANT, bars)
    return "long" if entries[-1] > 0 else "short" if entries[-1] < 0 else None
