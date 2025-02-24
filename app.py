from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
import asyncio
import json
import websockets
import logging

from config import EXCHANGES, parse_message

logging.basicConfig(level=logging.DEBUG)
logging.getLogger('websockets').setLevel(logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# We’ll designate one exchange as “fast” and let the user pick the “slow” exchange.
FAST_EXCHANGE = "binance"

# We’ll maintain a dictionary of dicts: { "binance": {}, "kraken": {}, etc.. }
prices = {ex: {} for ex in EXCHANGES}
ws_tasks = {}

async def start_exchange_ws(exchange: str, pair: str):
    """
    Opens a WS connection for a given exchange + pair, continuously tries to reconnect on error.
    """
    exchange_cfg = EXCHANGES[exchange]
    ws_url = exchange_cfg["ws_url"](exchange_cfg["pair_map"](pair))
    logger.info(f"{exchange} connecting to {ws_url}")

    while True:
        try:
            async with websockets.connect(ws_url) as ws:
                sub_msg = exchange_cfg["subscribe"](pair)
                if sub_msg:
                    await ws.send(json.dumps(sub_msg))
                    logger.info(f"{exchange} subscribed: {sub_msg}")

                async for raw in ws:
                    data = json.loads(raw)
                    for pair_name, price in parse_message(exchange, data):
                        prices[exchange][pair_name] = price
                        logger.debug(f"{exchange} updated price[{pair_name}]: {price}")
        except Exception as e:
            logger.error(f"{exchange} WebSocket error: {e}")
            await asyncio.sleep(1)  # wait briefly then reconnect

@app.get("/")
async def get():
    with open("templates/index.html") as f:
        return HTMLResponse(f.read())

@app.get("/exchanges")
async def get_exchanges():
    # Return the list of exchanges, excluding the “fast” one if you like
    # or keep it in, depending on UI preference.
    return list(EXCHANGES.keys())

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    current_asset = None
    current_exchange = None  # user-chosen "slow" exchange

    async def receive_messages():
        """
        Continuously read from the client. If the user changes asset or exchange,
        cancel old tasks and start new ones.
        """
        nonlocal current_asset, current_exchange
        while True:
            try:
                message = await websocket.receive_text()
                data = json.loads(message)
                new_asset = data.get("asset")
                new_exchange = data.get("exchange")

                # If user picks a new combination, restart tasks
                if new_asset and new_exchange and (new_asset != current_asset or new_exchange != current_exchange):
                    # Cancel existing tasks
                    for task in ws_tasks.values():
                        task.cancel()
                    ws_tasks.clear()

                    current_asset = new_asset
                    current_exchange = new_exchange

                    # Start WS tasks for both the FAST exchange and the user-chosen SLOW exchange
                    for ex in (FAST_EXCHANGE, current_exchange):
                        ws_tasks[ex] = asyncio.create_task(start_exchange_ws(ex, current_asset))
                    logger.info(f"Switched to asset: {current_asset}, exchange: {current_exchange}")

            except Exception as e:
                logger.error(f"WebSocket receive error: {e}")
                break

    async def send_updates():
        """
        Periodically send the client the latest price & difference info for the current asset.
        """
        while True:
            if current_asset and current_exchange:
                # Map the asset for each exchange
                fast_pair = EXCHANGES[FAST_EXCHANGE]["pair_map"](current_asset)
                slow_pair = EXCHANGES[current_exchange]["pair_map"](current_asset)

                fast_price = prices[FAST_EXCHANGE].get(fast_pair)
                slow_price = prices[current_exchange].get(slow_pair)

                # If the exchange has fallback logic (e.g. "kraken"), apply it
                fallback_fn = EXCHANGES[current_exchange].get("fallback_price")
                if slow_price is None and fallback_fn:
                    slow_price = fallback_fn(prices[current_exchange], current_asset, slow_pair)

                diff = None
                if fast_price and slow_price:
                    diff = abs(fast_price - slow_price) / fast_price * 100

                diff_data = {
                    "asset": current_asset,
                    "fast_pair": fast_pair,
                    "slow_pair": slow_pair,
                    "fast_price": fast_price,
                    "slow_price": slow_price,
                    "diff": diff
                }
                logger.info(
                    f"Sending - {FAST_EXCHANGE}[{fast_pair}]: {fast_price}, "
                    f"{current_exchange}[{slow_pair}]: {slow_price}, Diff: {diff}"
                )
                await websocket.send_text(json.dumps({"asset_diff": diff_data}))
            else:
                logger.debug("No asset/exchange set yet")
            await asyncio.sleep(0.1)

    receiver_task = asyncio.create_task(receive_messages())
    try:
        await send_updates()
    finally:
        receiver_task.cancel()
        for task in ws_tasks.values():
            task.cancel()
