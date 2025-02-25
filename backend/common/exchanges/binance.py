def ws_url(pair: str) -> str:
    """ Return the full Binance websocket URL for a given pair (e.g., btcusdt@trade). """
    return f"wss://stream.binance.com:9443/ws/{pair.lower()}@trade"

def pair_map(asset: str) -> str:
    """ For Binance, 'BTC/USDT' -> 'btcusdt' (lowercase, remove slash). """
    return asset.replace("/", "")

def subscribe(_: str):
    """ Binance does not require an explicit subscribe message (public trade stream). """
    return None

def parse(data: dict):
    """
    Binance trade event example:
    {
      "e": "trade",
      "s": "BTCUSDT",
      "p": "24448.16000000",
      ...
    }
    We return [("BTCUSDT", 24448.16)] if it's a trade event.
    """
    if data.get("e") == "trade":
        pair_name = data["s"]  # Uppercase from Binance
        return [(pair_name, float(data["p"]))]
    return []

# Export config
CONFIG = {
    "ws_url": ws_url,
    "pair_map": pair_map,
    "subscribe": subscribe,
    "parse": parse,
}