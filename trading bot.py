import time
from binance.exceptions import BinanceAPIException
from config import config
from binance_api import place_order, cancel_order, get_ticker_price, order_filled, get_open_orders
import concurrent.futures
import logging

logging.basicConfig(filename='long_trading_bot.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


symbol = config['symbol']
initial_order_volume = config['initial_order_volume']
take_profit_percentage = config['take_profit_percentage']

logging.info("grid_trading_bot.py variables:")
logging.info(f"symbol: {symbol}")
logging.info(f"initial_order_volume: {initial_order_volume}")
logging.info(f"take_profit_percentage: {take_profit_percentage}")

grid_step = 0.01
num_grids = 20


def update_grid_prices():
    global grid_prices
    grid_prices = [get_ticker_price() * (1 - grid_step * i) for i in range(num_grids)]

grid_prices = [get_ticker_price() * (1 - grid_step * i) for i in range(num_grids)]

def place_and_track_order(grid_index):

    while True:
        first_grid = (grid_index == 0)

        while True:
            price = grid_prices[grid_index]
            order_id = f'long_buy_{int(time.time() * 1000)}_{grid_index}'
            if first_grid:
                buy_order = place_order('BUY', price, initial_order_volume, order_id, 'LONG', 'MARKET')
            else:
                buy_order = place_order('BUY', price, initial_order_volume, order_id, 'LONG', 'LIMIT')
            logging.info(f'Long {grid_index}: {buy_order}')
            time.sleep(5)  

            while not order_filled(buy_order):
                time.sleep(5)

            price = grid_prices[grid_index] * (1 + take_profit_percentage)
            order_id_tp = f'tp_{int(time.time() * 1000)}'
            # Update the volume to 80% of the initial order volume
            tp_order = place_order('SELL', price, initial_order_volume*0.8, order_id_tp, 'LONG', 'LIMIT')
            logging.info(f'Long Profit {grid_index}: {tp_order}')
            time.sleep(5)  

            while not order_filled(tp_order):
                time.sleep(5)

            print(f'Take-profit order filled for grid_index {grid_index}')

            if first_grid:
                logging.info("First grid TP filled")
                cancel_grid_orders()
                logging.info(f'close all')
                update_grid_prices()
                return False

def cancel_grid_orders():
    open_orders = get_open_orders()
    for order in open_orders:
        if 'long_buy_' in order['order_id']:
            cancel_order(order['order_id'])  

def grid_trading():
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_grids) as executor:
        futures = [executor.submit(place_and_track_order, i) for i in range(num_grids)]

        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                if result is False:
                    grid_trading()  # Call grid_trading recursively to restart the cycle
                    return  # Exit the current call to grid_trading
            except BinanceAPIException as e:
                logging.error(f'Error: {e.message} (Code: {e.code})')

while True:
    try:
        grid_trading()
    except BinanceAPIException as e:
        logging.error(f'Error: {e.message} (Code: {e.code})')
        time.sleep(10)