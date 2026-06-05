import tkinter as tk
from tkinter import ttk
import MetaTrader5 as mt5
import sqlite3
from database import get_accounts_for_copier
import sys
import os
import subprocess
import threading
import time
from datetime import datetime
from tkinter import messagebox
from risk_manager import get_broker_symbol, calculate_lot, get_pip_size, calculate_risk_reward_ratio, get_deal_pnl, is_closed_copier_deal, get_risk_tracker, apply_trade_result_to_tracker, update_risk_tracker_from_history, get_managed_risk_percent

sys.path.append(os.path.dirname(os.path.abspath(__file__)))




symbols_pip_values = {'XAUUSD':1, 'GBPUSD':10}
trailing_running = False
COPIER_MAGIC = 10001
MIN_RISK_REWARD_RATIO = 1.5
REDUCED_RISK_PERCENT = 0.5
LOSS_STREAK_LIMIT = 3
RISK_TRACKER_STARTED_AT = datetime.now()
risk_trackers = {}
risk_tracker_lock = threading.Lock()

# === Your accounts ===
def get_enabled_accounts():
    return get_accounts_for_copier(enabled_only=True)



def open_account_manager():
    if getattr(sys, "frozen", False):
        subprocess.Popen([sys.executable, "--accounts"])
    else:
        subprocess.Popen([sys.executable, os.path.abspath(__file__), "--accounts"])

    


# === Copier logic ===


def place_trade_for_all_accounts(symbol, entry, sl, tp, order_type, pip_value, risk_percent=1, manual_lot=None):
    for acc in get_enabled_accounts():
        print(f"Connecting to account {acc['login']}...")
       

        if not mt5.initialize(path=acc['path'], login=int(acc['login']), password=acc['password'], server=acc['server']):
            print(f"Connection failed: {mt5.last_error()}")
            continue

        acc_info = mt5.account_info()
        if acc_info is None:
            print("Failed to get account info")
            mt5.shutdown()
            continue

        login = str(acc["login"])
        update_risk_tracker_from_history(login)

        rr_ratio = calculate_risk_reward_ratio(entry, sl, tp, order_type)
        if rr_ratio is None:
            print(f"Skipped trade for {login}: invalid SL/TP for {order_type}.")
            mt5.shutdown()
            continue

        if rr_ratio < MIN_RISK_REWARD_RATIO:
            print(
                f"Skipped trade for {login}: RR {rr_ratio:.2f} is below "
                f"1:{MIN_RISK_REWARD_RATIO}."
            )
            mt5.shutdown()
            continue

        if manual_lot is not None:
            lot = manual_lot
       
        else:
            managed_risk_percent = get_managed_risk_percent(login, risk_percent)
            lot = calculate_lot(acc_info.balance, entry, sl, risk_percent=managed_risk_percent, pip_value_per_lot=pip_value)

        risk_label = "manual lot" if manual_lot is not None else f"Risk: {managed_risk_percent}%"
        print(f"Account: {login}, Balance: {acc_info.balance}, Lot: {lot}, {risk_label}, RR: {rr_ratio:.2f}")
        broker_symbol = get_broker_symbol(symbol)
        if not broker_symbol:
            print(f"❌ No matching symbol for {symbol}")
            mt5.shutdown()
            continue
        tick = mt5.symbol_info_tick(broker_symbol)

        if tick is None:
            print(f"❌ Failed to get tick for {broker_symbol}")
            mt5.shutdown()
            continue

        request = {
            "action": mt5.TRADE_ACTION_DEAL if "market" in order_type else mt5.TRADE_ACTION_PENDING,
            "symbol": broker_symbol,
            "volume": lot,
            "type": {
                "market_buy": mt5.ORDER_TYPE_BUY,
                "market_sell": mt5.ORDER_TYPE_SELL,
                "buy_stop": mt5.ORDER_TYPE_BUY_STOP,
                "sell_stop": mt5.ORDER_TYPE_SELL_STOP,
            }[order_type],
            "price": entry if "stop" in order_type else mt5.symbol_info_tick(broker_symbol).ask if "buy" in order_type else mt5.symbol_info_tick(broker_symbol).bid,
            "sl": sl,
            "tp": tp if tp > 0 else 0.0,
            "deviation": 20,
            "magic": COPIER_MAGIC,
            "comment": "Trade Copier UI",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC
        }

        result = mt5.order_send(request)
        print("Trade result:", result)
        mt5.shutdown()


def close_all_positions():
    for acc in get_enabled_accounts():
        print(f"Closing trades for account {acc['login']}...")

        if not mt5.initialize(path=acc['path'], login=int(acc['login']), password=acc['password'], server=acc['server']):
            print(f"Connection failed: {mt5.last_error()}")
            continue

        positions = mt5.positions_get()

        if positions:
            for pos in positions:
                symbol = pos.symbol
                volume = pos.volume

                tick = mt5.symbol_info_tick(symbol)
                if tick is None:
                    print(f"Failed to get tick for {symbol}")
                    continue

                price = tick.bid if pos.type == mt5.POSITION_TYPE_BUY else tick.ask

                close_request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": symbol,
                    "volume": volume,
                    "type": mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY,
                    "position": pos.ticket,
                    "price": price,
                    "deviation": 20,
                    "magic": COPIER_MAGIC,
                    "comment": "Auto Close",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }

                result = mt5.order_send(close_request)
                print("Close result:", result)

        mt5.shutdown() 


def monitor_profit_loss(target_profit, max_loss):
    global running
    running = True

    while running:
        total_profit = 0

        for acc in get_enabled_accounts():
            if not mt5.initialize(path=acc['path'], login=int(acc['login']), password=acc['password'], server=acc['server']):
                continue

            positions = mt5.positions_get()
            if positions:
                total_profit += sum(pos.profit for pos in positions)

            mt5.shutdown()
            time.sleep(2)
        print(f"Current Total Profit: {total_profit}") 
        if total_profit >= target_profit:
            print("✅ Target profit reached! Closing all trades...")
            close_all_positions()
            break

        if total_profit <= -abs(max_loss):
            print("❌ Max loss hit! Closing all trades...")
            close_all_positions()
            break
def stop_auto_close():
    global running
    running = False
    print("🛑 Auto-close stopped.")


def get_total_profit():
    total_profit = 0

    for acc in get_enabled_accounts():
        if not mt5.initialize(path=acc['path'], login=int(acc['login']), password=acc['password'], server=acc['server']):
            continue

        positions = mt5.positions_get()
        if positions:
            total_profit += sum(pos.profit for pos in positions)

        mt5.shutdown()

    return total_profit
  
def close_partial(percent):
    for acc in get_enabled_accounts():
        print(f"Partial close ({percent}%) for account {acc['login']}...")

        if not mt5.initialize(path=acc['path'], login=int(acc['login']), password=acc['password'], server=acc['server']):
            print("Connection failed")
            continue

        positions = mt5.positions_get()

        if positions:
            for pos in positions:
                symbol = pos.symbol
                volume = pos.volume

                close_volume = round(volume * (percent / 100), 2)

                tick = mt5.symbol_info_tick(symbol)
                if tick is None:
                    continue

                price = tick.bid if pos.type == mt5.POSITION_TYPE_BUY else tick.ask

                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": symbol,
                    "volume": close_volume,
                    "type": mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY,
                    "position": pos.ticket,
                    "price": price,
                    "deviation": 20,
                    "magic": COPIER_MAGIC,
                    "comment": "Partial Close",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }

                result = mt5.order_send(request)
                print("Partial result:", result)

        mt5.shutdown()

def move_to_breakeven():
    for acc in get_enabled_accounts():
        print(f"Breakeven for account {acc['login']}...")

        if not mt5.initialize(path=acc['path'], login=int(acc['login']), password=acc['password'], server=acc['server']):
            print("Connection failed")
            continue

        positions = mt5.positions_get()

        if positions:
            for pos in positions:
                entry_price = pos.price_open

                request = {
                    "action": mt5.TRADE_ACTION_SLTP,
                    "symbol": pos.symbol,
                    "position": pos.ticket,
                    "sl": entry_price,  # 🔥 move SL to entry
                    "tp": pos.tp,
                }

                result = mt5.order_send(request)
                print("Breakeven result:", result)

        mt5.shutdown()

def monitor_trailing_stop(trail_pips, check_interval=1):
    global trailing_running

    if trail_pips <= 0:
        print("Trail distance must be greater than 0.")
        return

    if trailing_running:
        print("Trailing stop is already running.")
        return

    trailing_running = True
    print(f"Trailing stop started at {trail_pips} pips.")

    while trailing_running:
        for acc in get_enabled_accounts():
            if not trailing_running:
                break

            if not mt5.initialize(path=acc['path'], login=int(acc['login']), password=acc['password'], server=acc['server']):
                print(f"Connection failed: {mt5.last_error()}")
                continue

            positions = mt5.positions_get()

            if positions:
                for pos in positions:
                    tick = mt5.symbol_info_tick(pos.symbol)
                    symbol_info = mt5.symbol_info(pos.symbol)

                    if tick is None or symbol_info is None:
                        print(f"Failed to get symbol data for {pos.symbol}")
                        continue

                    min_stop_distance = symbol_info.trade_stops_level * symbol_info.point

                    if pos.type == mt5.POSITION_TYPE_BUY:
                        current_price = tick.bid
                        trail_distance = max(trail_pips * get_pip_size(current_price), min_stop_distance)
                        new_sl = current_price - trail_distance

                        if current_price - pos.price_open < trail_distance:
                            continue

                        if pos.sl and new_sl <= pos.sl:
                            continue

                    elif pos.type == mt5.POSITION_TYPE_SELL:
                        current_price = tick.ask
                        trail_distance = max(trail_pips * get_pip_size(current_price), min_stop_distance)
                        new_sl = current_price + trail_distance

                        if pos.price_open - current_price < trail_distance:
                            continue

                        if pos.sl and new_sl >= pos.sl:
                            continue

                    else:
                        continue

                    new_sl = round(new_sl, symbol_info.digits)

                    request = {
                        "action": mt5.TRADE_ACTION_SLTP,
                        "symbol": pos.symbol,
                        "position": pos.ticket,
                        "sl": new_sl,
                        "tp": pos.tp,
                    }

                    result = mt5.order_send(request)
                    print(f"Trailing SL result for {pos.symbol} #{pos.ticket}: {result}")

            mt5.shutdown()

        time.sleep(check_interval)

def stop_trailing_stop():
    global trailing_running
    trailing_running = False
    print("Trailing stop stopped.")

def set_stop_loss_price_for_all_accounts(sl_price, base_symbol=None):
    if sl_price <= 0:
        print("Stop loss price must be greater than 0.")
        return

    base_symbol = base_symbol.strip().upper() if base_symbol else None

    for acc in get_enabled_accounts():
        print(f"Setting SL to {sl_price} for account {acc['login']}...")

        if not mt5.initialize(path=acc['path'], login=int(acc['login']), password=acc['password'], server=acc['server']):
            print(f"Connection failed: {mt5.last_error()}")
            continue

        positions = mt5.positions_get()

        if positions:
            for pos in positions:
                if base_symbol and not pos.symbol.upper().startswith(base_symbol):
                    continue

                tick = mt5.symbol_info_tick(pos.symbol)
                symbol_info = mt5.symbol_info(pos.symbol)

                if tick is None or symbol_info is None:
                    print(f"Failed to get symbol data for {pos.symbol}")
                    continue

                new_sl = round(sl_price, symbol_info.digits)
                min_stop_distance = symbol_info.trade_stops_level * symbol_info.point

                if pos.type == mt5.POSITION_TYPE_BUY and tick.bid - new_sl < min_stop_distance:
                    print(f"Skipped {pos.symbol} #{pos.ticket}: SL must be below current bid.")
                    continue

                if pos.type == mt5.POSITION_TYPE_SELL and new_sl - tick.ask < min_stop_distance:
                    print(f"Skipped {pos.symbol} #{pos.ticket}: SL must be above current ask.")
                    continue

                request = {
                    "action": mt5.TRADE_ACTION_SLTP,
                    "symbol": pos.symbol,
                    "position": pos.ticket,
                    "sl": new_sl,
                    "tp": pos.tp,
                }

                result = mt5.order_send(request)
                print(f"Set SL result for {pos.symbol} #{pos.ticket}: {result}")

        mt5.shutdown()

def run_ui():
    from ui import launch_ui,launch_floating_panel,launch_account_manager
    if "--accounts" in sys.argv:
        launch_account_manager()
    else:
        threading.Thread(target=launch_ui, daemon=True).start()
        launch_floating_panel()
        launch_ui()

if __name__ == "__main__":
    run_ui()