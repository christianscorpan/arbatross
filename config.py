import logging
from exchanges.binance import CONFIG as BINANCE_CONFIG
from exchanges.kraken import CONFIG as KRAKEN_CONFIG
from exchanges.mexc import CONFIG as MEXC_CONFIG

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

EXCHANGES = {
    "binance": BINANCE_CONFIG,
    "kraken": KRAKEN_CONFIG,
    "mexc": MEXC_CONFIG,
}

def parse_message(exchange: str, data: dict):
    """
    Generic parse entrypoint. If anything goes wrong, log it and return [].
    """
    try:
        return EXCHANGES[exchange]["parse"](data)
    except Exception as e:
        logger.error(f"Error parsing {exchange} data: {e}, received: {data}")
        return []