from fastapi import FastAPI, WebSocket
import asyncio
import json
import websockets
import logging
from backend.common.config import EXCHANGES, parse_message

# Logging setup
logging.basicConfig(level=logging.DEBUG)
logging.getLogger('websockets').setLevel(logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
FAST_EXCHANGE = "binance"
prices = {ex: {} for ex in EXCHANGES}
ws_tasks = {}

async def start_exchange_ws(exchange: str, pair: str):
    """
    Opens a WebSocket connection for a given exchange + pair, with reconnection on error.
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
            await asyncio.sleep(1)

@app.get("/exchanges")
async def get_exchanges():
    """Returns list of available exchanges, excluding the fast one."""
    return [ex for ex in EXCHANGES.keys() if ex != FAST_EXCHANGE]

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Handles WebSocket connections for price difference updates."""
    await websocket.accept()
    current_asset = None
    current_exchange = None

    async def receive_messages():
        nonlocal current_asset, current_exchange
        while True:
            try:
                data = json.loads(await websocket.receive_text())
                new_asset, new_exchange = data.get("asset"), data.get("exchange")
                if new_asset and new_exchange and (new_asset != current_asset or new_exchange != current_exchange):
                    for task in ws_tasks.values():
                        task.cancel()
                    ws_tasks.clear()
                    current_asset, current_exchange = new_asset, new_exchange
                    for ex in (FAST_EXCHANGE, current_exchange):
                        ws_tasks[ex] = asyncio.create_task(start_exchange_ws(ex, current_asset))
                    logger.info(f"Switched to asset: {current_asset}, exchange: {current_exchange}")
            except Exception as e:
                logger.error(f"WebSocket receive error: {e}")
                break

    async def send_updates():
        while True:
            if current_asset and current_exchange:
                fast_pair = EXCHANGES[FAST_EXCHANGE]["pair_map"](current_asset)
                slow_pair = EXCHANGES[current_exchange]["pair_map"](current_asset)
                fast_price = prices[FAST_EXCHANGE].get(fast_pair)
                slow_price = prices[current_exchange].get(slow_pair)
                diff = abs(fast_price - slow_price) / fast_price * 100 if fast_price and slow_price else None
                await websocket.send_text(json.dumps({
                    "asset_diff": {
                        "asset": current_asset,
                        "fast_price": fast_price,
                        "slow_price": slow_price,
                        "diff": diff,
                        "fast_pair": fast_pair,
                        "slow_pair": slow_pair
                    }
                }))
            await asyncio.sleep(0.1)

    receiver_task = asyncio.create_task(receive_messages())
    try:
        await send_updates()
    finally:
        receiver_task.cancel()
        for task in ws_tasks.values():
            task.cancel()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
