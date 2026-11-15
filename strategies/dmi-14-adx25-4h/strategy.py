"""Fixed dmi experiment rule; frozen source signals are reused."""
from src.research.classic_indicator_grid import signals_for_method
STRATEGY_ID = 'dmi-14-adx25-4h'
TIMEFRAME = '4H'
VARIANT = 'dmi_14_adx25'
PAPER_SYMBOLS = ['WUSH', 'CBOM', 'RUAL', 'VKCO', 'HYDR', 'SGZH', 'MTLR', 'X5']
def signal(bars):
    if not bars:
        return None
    entries, _ = signals_for_method('dmi', VARIANT, bars)
    return "long" if entries[-1] > 0 else "short" if entries[-1] < 0 else None
