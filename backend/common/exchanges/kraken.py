def ws_url(_: str) -> str:
    """ Kraken has a single WS URL; the actual subscription is done via messages. """
    return "wss://ws.kraken.com"

def pair_map(asset: str) -> str:
    """
    Kraken uses XBT instead of BTC, etc. 
    'BTC/USDT' -> 'XBT/USDT'
    'ETH/BTC'  -> 'ETH/XBT'
    """
    return asset.replace("BTC", "XBT")

def subscribe(asset: str):
    """
    Kraken ticker subscription example:
      {
        "event": "subscribe",
        "pair": [
            "XBT/USDT",
            "XBT/USD"    # fallback subscription if USDT is not available
        ],
        "subscription": { "name": "ticker" }
      }
    """
    mapped = pair_map(asset)
    return {
        "event": "subscribe",
        "pair": [
            mapped,
            mapped.replace("/USDT", "/USD")
        ],
        "subscription": {"name": "ticker"}
    }

def parse(data):
    """
    Kraken ticker event example:
      [
        42,
        { "c": ["24448.1", "1.2345"], ... },
        "ticker",
        "XBT/USDT"
      ]
    Check if it’s a ticker message and parse accordingly. Return [("XBT/USDT", price_float)].
    """
    if isinstance(data, list) and len(data) > 3:
        ticker_info = data[1]
        pair_name = data[3]
        if isinstance(ticker_info, dict) and "c" in ticker_info:
            last_trade_price = float(ticker_info["c"][0])
            return [(pair_name, last_trade_price)]
    return []

def fallback_price(prices_dict: dict, asset: str, mapped_pair: str):
    """
    Example fallback logic:
    If the “/USDT” pair is missing, try the “/USD” version.
    This is called only if the normal price lookup was None.
    """
    if asset.endswith("/USDT"):
        usd_asset = asset.replace("/USDT", "/USD")
        usd_pair = pair_map(usd_asset)
        return prices_dict.get(usd_pair)
    return None

# Export config
CONFIG = {
    "ws_url": ws_url,
    "pair_map": pair_map,
    "subscribe": subscribe,
    "parse": parse,
    "fallback_price": fallback_price
}