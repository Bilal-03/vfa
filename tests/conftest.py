"""Offline tests never read or write the connected market-data cache."""
import os
os.environ['MARKET_CACHE_ENABLED'] = 'false'
