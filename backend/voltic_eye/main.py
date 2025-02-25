from fastapi import FastAPI, WebSocket
import asyncio
import json
import websockets
import logging
import aiohttp
import time
from collections import defaultdict, deque
from backend.common.config import EXCHANGES, parse_message

# Logging setup
logging.basicConfig(level=logging.DEBUG)
logging.getLogger('websockets').setLevel(logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
BINANCE = "binance"
# Store minute-by-minute price data for each pair
prices = defaultdict(lambda: deque(maxlen=60))  # 60 second window
ws_tasks = []
last_refresh = 0
REFRESH_INTERVAL = 300  # Refresh hotlist every 5 minutes
MAX_PAIRS = 50  # Monitor top 50 volatile pairs

async def get_volatile_pairs():
    """Fetch top volatile pairs from Binance's 24hr stats."""
    async with aiohttp.ClientSession() as session:
        async with session.get('https://api.binance.com/api/v3/ticker/24hr') as response:
            data = await response.json()
            # Calculate volatility (high-low)/low for USDT pairs
            volatility = []
            for item in data:
                if item['symbol'].endswith('USDT'):
                    high = float(item['highPrice'])
                    low = float(item['lowPrice'])
                    vol = ((high - low) / low * 100) if low > 0 else 0
                    volatility.append((item['symbol'], vol))
            # Return top volatile pairs
            return [pair for pair, _ in sorted(volatility, key=lambda x: x[1], reverse=True)[:MAX_PAIRS]]

async def start_binance_ws(symbol: str):
    """
    Opens a WebSocket connection to Binance for a pair.
    Maintains a sliding 60-second window of prices for volatility calculation.
    """
    ws_url = f"wss://stream.binance.com:9443/ws/{symbol.lower()}@trade"
    logger.info(f"Connecting to Binance WS for {symbol}")
    while True:
        try:
            async with websockets.connect(ws_url) as ws:
                async for raw in ws:
                    data = json.loads(raw)
                    if data.get("e") == "trade":
                        price = float(data["p"])
                        timestamp = int(time.time())
                        prices[symbol].append((timestamp, price))
        except Exception as e:
            logger.error(f"Binance WS error for {symbol}: {e}")
            await asyncio.sleep(1)

def calculate_volatility(price_data):
    """Calculate volatility from price data in the last minute."""
    if len(price_data) < 2:
        return 0
    
    now = int(time.time())
    minute_ago = now - 60
    # Filter prices from last minute
    recent_prices = [p for t, p in price_data if t >= minute_ago]
    
    if len(recent_prices) < 2:
        return 0
        
    min_price = min(recent_prices)
    max_price = max(recent_prices)
    return ((max_price - min_price) / min_price * 100) if min_price > 0 else 0

async def get_24hr_volatility():
    """Get immediate volatility data from 24hr stats."""
    async with aiohttp.ClientSession() as session:
        async with session.get('https://api.binance.com/api/v3/ticker/24hr') as response:
            data = await response.json()
            volatility = []
            for item in data:
                if item['symbol'].endswith('USDT'):
                    high = float(item['highPrice'])
                    low = float(item['lowPrice'])
                    vol = ((high - low) / low * 100) if low > 0 else 0
                    volatility.append((item['symbol'], vol))
            return sorted(volatility, key=lambda x: x[1], reverse=True)[:10]

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Sends real-time updates of top volatile pairs to connected clients."""
    global last_refresh
    await websocket.accept()
    
    try:
        # Send immediate 24hr volatility data
        initial_volatility = await get_24hr_volatility()
        await websocket.send_text(json.dumps({
            "top_volatile": [
                {"pair": pair, "volatility": vol} 
                for pair, vol in initial_volatility
            ]
        }))
        
        # Get pairs to monitor
        pairs = await get_volatile_pairs()
        last_refresh = int(time.time())
        logger.info(f"Monitoring top {len(pairs)} volatile pairs")
        
        # Start monitoring these pairs
        for pair in pairs:
            ws_tasks.append(asyncio.create_task(start_binance_ws(pair)))
        
        while True:
            now = int(time.time())
            
            # Refresh hotlist every 5 minutes
            if now - last_refresh >= REFRESH_INTERVAL:
                # Cancel old tasks
                for task in ws_tasks:
                    task.cancel()
                ws_tasks.clear()
                prices.clear()
                
                # Get new hotlist and start monitoring
                pairs = await get_volatile_pairs()
                last_refresh = now
                logger.info(f"Refreshed hotlist: {len(pairs)} pairs")
                for pair in pairs:
                    ws_tasks.append(asyncio.create_task(start_binance_ws(pair)))
            
            # Calculate current volatility from price data
            volatility = {}
            for symbol, price_data in prices.items():
                vol = calculate_volatility(price_data)
                if vol > 0:  # Only include pairs with some volatility
                    volatility[symbol] = vol
            
            # Get current top volatile pairs
            top_pairs = sorted(volatility.items(), key=lambda x: x[1], reverse=True)[:10]
            await websocket.send_text(json.dumps({
                "top_volatile": [
                    {"pair": pair, "volatility": vol} 
                    for pair, vol in top_pairs
                ]
            }))
            
            await asyncio.sleep(1)  # Update every second
    
    finally:
        # Cleanup when client disconnects
        for task in ws_tasks:
            task.cancel()
        ws_tasks.clear()
        prices.clear()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
