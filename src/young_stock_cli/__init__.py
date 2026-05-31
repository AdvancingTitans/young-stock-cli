"""young-stock-cli: A-share/HK/US stock market CLI.

A no-login, anti-bot-aware market data CLI built on Eastmoney's public
endpoints. Provides afternoon/post-market replays, sector rankings, and
sentiment snapshots for the Chinese, Hong Kong, and US equity markets.

Quick start::

    young a              # A-share post-market replay
    young hk             # Hong Kong replay
    young us             # US replay
    young global         # Global indices snapshot
    young a 20260526     # Specific trading day
"""
from .__version__ import __version__

__all__ = ["__version__"]
