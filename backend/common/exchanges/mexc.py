def ws_url(_: str) -> str:
    """ MEXC uses a single WS URL; subscription is via message. """
    return "wss://wbs.mexc.com/ws"

def pair_map(asset: str) -> str:
    """ For MEXC, 'BTC/USDT' -> 'BTCUSDT' (uppercase, remove slash). """
    return asset.replace("/", "")

def subscribe(asset: str):
    """
    MEXC subscription example:
    {
      "method": "SUBSCRIPTION",
      "params": ["spot@public.bookTicker.v3.api@BTCUSDT"],
      "id": 1
    }
    """
    mapped = pair_map(asset)
    return {
        "method": "SUBSCRIPTION",
        "params": [f"spot@public.bookTicker.v3.api@{mapped}"],
        "id": 1
    }

def parse(data: dict):
    """
    MEXC bookTicker event example:
    {
      "d": {"a": "24448.16", "b": "24447.50"},
      "c": "spot@public.bookTicker.v3.api@BTCUSDT",
      "s": "BTCUSDT"
    }
    Returns [("BTCUSDT", 24448.16)] using best ask price.
    """
    if "d" in data and "a" in data["d"] and "s" in data:
        pair_name = data["s"]  # Keep as BTCUSDT to match pair_map
        return [(pair_name, float(data["d"]["a"]))]
    return []

# Export config
CONFIG = {
    "ws_url": ws_url,
    "pair_map": pair_map,
    "subscribe": subscribe,
    "parse": parse,
}