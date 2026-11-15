"""Fixed keltner experiment rule; frozen source signals are reused."""
from src.research.classic_indicator_grid import signals_for_method
STRATEGY_ID = 'keltner-30-wide-4h'
TIMEFRAME = '4H'
VARIANT = 'keltner_30_wide'
PAPER_SYMBOLS = ['X5', 'WUSH', 'MTLR', 'SMLT', 'RUAL', 'ENPG', 'VKCO', 'PHOR', 'SFIN', 'UGLD', 'ALRS', 'BELU', 'SGZH']
def signal(bars):
    if not bars:
        return None
    entries, _ = signals_for_method('keltner', VARIANT, bars)
    return "long" if entries[-1] > 0 else "short" if entries[-1] < 0 else None
