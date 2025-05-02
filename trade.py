import os
import json
import asyncio
import logging
import aiohttp
from decimal import Decimal, ROUND_DOWN
from binance.enums import SIDE_SELL, ORDER_TYPE_MARKET
from binance.exceptions import BinanceAPIException, BinanceOrderException
from binance import AsyncClient, BinanceSocketManager

# Load config from file
def load_config(filepath="config.json"):
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("Config file not found. Ensure config.json exists in the script directory.")
        exit(1)
    except json.JSONDecodeError:
        print("Invalid JSON format in config.json. Please check your config file.")
        exit(1)

# Read config early to determine testnet mode for logging
_config = load_config()
testnet_mode = _config.get("testnet", True)
debug_ws_logging = _config.get("debug_ws_logging", False)
_log_file = "trade-testnet.log" if testnet_mode else "trade-mainnet.log"
_raw_ws_log = "raw-ws-testnet.log" if testnet_mode else "raw-ws-mainnet.log"

# Set up logging to both console and separate file per environment
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(_log_file)
    ]
)

# Write a clean line break for new run
with open(_log_file, "a") as f:
    f.write("\n-------------------- NEW RUN --------------------\n")

if debug_ws_logging:
    with open(_raw_ws_log, "a") as f:
        f.write("\n-------------------- RAW WS STREAM --------------------\n")


async def main():
    config = _config

    api_key = config.get('testnet_api_key') if testnet_mode else config.get('api_key')
    api_secret = config.get('testnet_api_secret') if testnet_mode else config.get('api_secret')

    symbol = config.get('symbol')
    price_rise_threshold_seconds = config.get("price_rise_threshold_seconds", 2)
    trailing_auto_cancel_seconds = config.get('trailing_auto_cancel_seconds', 30)
    discord_webhook = config.get('discord_webhook')

    if not all([api_key, api_secret, symbol]):
        logging.error("Missing API key, secret, or symbol in config file.")
        exit(1)

    logging.info(f"Starting script for symbol: {symbol}, Testnet Mode: {testnet_mode}")

    client = await AsyncClient.create(api_key, api_secret, testnet=testnet_mode)
    bm = BinanceSocketManager(client)

    trade_executed = False
    is_rising = True
    start_price = None
    last_price = None
    rising_start_time = None
    trailing_delta_percent = None
    final_total_usd = None

    async def send_discord_notification(message):
        if not discord_webhook:
            return
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(discord_webhook, json={"content": message})
        except Exception as e:
            logging.error(f"Failed to send Discord notification: {e}")

    async def format_order_notification(order, order_type):
        try:
            if not order:
                return f"{order_type.title()} Sell Failed: No order data returned."

            fills = order.get('fills', [{}])[0]
            price = fills.get('price', 'N/A')
            qty = fills.get('qty', 'N/A')
            total = order.get('cummulativeQuoteQty', 'N/A')
            nonlocal final_total_usd
            final_total_usd = total
            emoji = "📉" if order_type == 'MARKET' else "📈"
            return (
                f"{emoji} {order_type.title()} Sell Executed!\n"
                f"Symbol: {order.get('symbol')}\n"
                f"Amount Sold: {qty}\n"
                f"Avg Price: {price} USDC\n"
                f"Total: {total} USDC\n"
                f"Status: {order.get('status')}"
            )
        except Exception as e:
            logging.error(f"Failed to format Discord message: {e}")
            return f"{order_type.title()} Sell Executed, but failed to format message."

    async def ensure_test_balance():
        asset = symbol.replace('USDT', '').replace('USDC', '')
        balance = await client.get_asset_balance(asset=asset)
        if float(balance['free']) == 0:
            logging.info("Balance is zero, buying small amount for testing.")
            try:
                order = await client.order_market_buy(symbol=symbol, quantity=1)
                logging.info(f"Successfully bought test asset: {order}")
            except Exception as e:
                logging.error(f"Could not buy test asset: {e}")

    if testnet_mode:
        await ensure_test_balance()

    async def sell_at_market():
        try:
            asset = symbol.replace('USDT', '').replace('USDC', '')
            balance = await client.get_asset_balance(asset=asset)
            available_balance = float(balance['free'])
            symbol_info = await client.get_symbol_info(symbol)
            step_size = next(f for f in symbol_info['filters'] if f['filterType'] == 'LOT_SIZE')['stepSize']

            # Truncate to whole number
            available_balance = int(available_balance)

            logging.info(f"Available Balance after truncating to whole number: {available_balance}")
            if available_balance == 0:
                logging.warning("No balance available to sell. Exiting.")
                return

            logging.info("Placing market sell order...")
            order = await client.order_market_sell(symbol=symbol, quantity=available_balance)
            if not order:
                logging.error("Market Sell failed: order object was None.")
                await send_discord_notification(f"❌ Market Sell Failed: Binance returned None for {symbol}.")
                return

            logging.info(f"Market Sell Order executed: {order}")
            message = await format_order_notification(order, 'MARKET')
            await send_discord_notification(message)
        except (BinanceAPIException, BinanceOrderException) as e:
            logging.error(f"Binance Exception: {e}")
            await send_discord_notification(f"❌ Binance Error during Market Sell: {e}")
        except Exception as e:
            logging.error(f"Unexpected error during market sell: {e}")
            await send_discord_notification(f"❌ Unknown error during Market Sell: {e}")

    async def sell_with_trailing_stop(trailing_percent):
        try:
            asset = symbol.replace('USDT', '').replace('USDC', '')
            balance = await client.get_asset_balance(asset=asset)
            available_balance = float(balance['free'])
            symbol_info = await client.get_symbol_info(symbol)
            step_size = next(f for f in symbol_info['filters'] if f['filterType'] == 'LOT_SIZE')['stepSize']
            available_balance = float(Decimal(available_balance).quantize(Decimal(step_size), rounding=ROUND_DOWN))

            if available_balance == 0:
                logging.warning("No balance to sell via trailing stop.")
                return

            if testnet_mode:
                logging.info("Testnet mode: Simulating trailing stop logic with market sell.")
                await sell_at_market()
                return

            order = await client.create_order(
                symbol=symbol,
                side=SIDE_SELL,
                type='TRAILING_STOP_MARKET',
                quantity=available_balance,
                callbackRate=trailing_percent
            )
            if not order:
                logging.error("Trailing stop order failed: order object was None.")
                await send_discord_notification(f"❌ Trailing Stop Order Failed: Binance returned None for {symbol}.")
                return

            logging.info(f"Trailing Stop Order placed: {order}")
            message = await format_order_notification(order, 'TRAILING_STOP')
            await send_discord_notification(message)

            await asyncio.sleep(trailing_auto_cancel_seconds)
            check = await client.get_order(symbol=symbol, orderId=order['orderId'])
            if check['status'] == 'NEW':
                logging.info(f"Trailing stop not triggered in {trailing_auto_cancel_seconds}s. Cancelling and selling at market.")
                await client.cancel_order(symbol=symbol, orderId=order['orderId'])
                await sell_at_market()
            else:
                logging.info("Trailing stop was triggered before timeout.")
        except Exception as e:
            logging.error(f"Error in trailing stop order: {e}")

    async def process_message(msg):
        nonlocal is_rising, start_price, last_price, rising_start_time, trade_executed, trailing_delta_percent

        # Stream raw WebSocket message to separate log file for debugging
        if debug_ws_logging:
            with open(_raw_ws_log, "a") as f:
                f.write(json.dumps(msg) + "\n")

        if trade_executed:
            return

        if msg['e'] == 'error':
            logging.error(f"WebSocket Error: {msg}")
            return

        current_price = Decimal(msg['p'])

        if start_price is None:
            start_price = current_price
            last_price = current_price
            rising_start_time = asyncio.get_event_loop().time()
            if current_price >= 1:
                trailing_delta_percent = 1.0
            elif current_price >= 0.1:
                trailing_delta_percent = 0.75
            else:
                trailing_delta_percent = 0.5
            logging.info(f"First price received: {current_price}, Trailing set to {trailing_delta_percent}%")
            return

        if current_price <= last_price:
            is_rising = False
            rise_duration = asyncio.get_event_loop().time() - rising_start_time
            logging.info(f"Price stopped rising after {rise_duration:.2f} seconds.")

            if rise_duration < price_rise_threshold_seconds:
                logging.info("Price declined before threshold. Executing market sell.")
                await sell_at_market()
            else:
                logging.info("Price rose enough. Executing trailing stop.")
                await sell_with_trailing_stop(trailing_delta_percent)
            trade_executed = True
            await client.close_connection()
            return

        last_price = current_price
        if is_rising:
            rise_duration = asyncio.get_event_loop().time() - rising_start_time
            logging.info(f"Price rising... duration: {rise_duration:.2f}s, price: {current_price}")
        else:
            is_rising = True
            rising_start_time = asyncio.get_event_loop().time()
            logging.info(f"Price rising again at: {current_price}")

    try:
        ts = bm.trade_socket(symbol)
        async with ts as tscm:
            while not trade_executed:
                msg = await tscm.recv()
                await process_message(msg)
    except Exception as e:
        logging.error(f"WebSocket connection error: {e}")
    finally:
        logging.info("Closing WebSocket connection.")
        await client.close_connection()
        await asyncio.sleep(0.5)

        if final_total_usd and not testnet_mode:
            logging.info(f"Final sale total: {final_total_usd} USDC")
            await send_discord_notification(f"📊 Final Sale Total: {final_total_usd} USDC")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Script interrupted.")
        logging.info("Script finished.")
