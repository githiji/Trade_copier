import tkinter as tk
from tkinter import ttk
import MetaTrader5 as mt5
import sqlite3
from database import get_accounts_for_copier
import sys
import os

# Ensure current dir is in path for local imports to work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))



symbols_pip_values = {'XAUUSD':1, 'GBPUSD':10}

# === Your accounts ===
accounts = [acc for acc in get_accounts_for_copier() if acc.get('enabled') == 1]
    
    


# === Utility functions ===
def calculate_lot(balance, entry_price, sl_price, risk_percent=1, pip_value_per_lot=10):
    point = 0.01 if entry_price > 100 else 0.0001
    stop_loss_pips = abs(entry_price - sl_price) / point
    risk_amount = balance * (risk_percent / 100)
    lot = risk_amount / (stop_loss_pips * pip_value_per_lot)
    return round(lot, 2)

def place_trade_for_all_accounts(symbol, entry, sl, tp, order_type, pip_value, risk_percent=1, manual_lot=None):
    for acc in accounts:
        print(f"Connecting to account {acc['login']}...")

        if not mt5.initialize(path=acc['path'], login=int(acc['login']), password=acc['password'], server=acc['server']):
            print(f"Connection failed: {mt5.last_error()}")
            continue

        acc_info = mt5.account_info()
        if acc_info is None:
            print("Failed to get account info")
            mt5.shutdown()
            continue

        if manual_lot is not None:
            lot = manual_lot
        else:
            lot = calculate_lot(acc_info.balance, entry, sl, risk_percent=risk_percent, pip_value_per_lot=pip_value)

        print(f"Account: {acc['login']}, Balance: {acc_info.balance}, Lot: {lot}")

        request = {
            "action": mt5.TRADE_ACTION_DEAL if "market" in order_type else mt5.TRADE_ACTION_PENDING,
            "symbol": symbol,
            "volume": lot,
            "type": {
                "market_buy": mt5.ORDER_TYPE_BUY,
                "market_sell": mt5.ORDER_TYPE_SELL,
                "buy_stop": mt5.ORDER_TYPE_BUY_STOP,
                "sell_stop": mt5.ORDER_TYPE_SELL_STOP,
            }[order_type],
            "price": entry if "stop" in order_type else mt5.symbol_info_tick(symbol).ask if "buy" in order_type else mt5.symbol_info_tick(symbol).bid,
            "sl": sl,
            "tp": tp if tp > 0 else 0.0,
            "deviation": 20,
            "magic": 10001,
            "comment": "Trade Copier UI",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC
        }

        result = mt5.order_send(request)
        print("Trade result:", result)
        mt5.shutdown()

# === UI ===
def launch_ui():
    window = tk.Tk()
    window.title("Trade Copier")
    window.geometry("280x450")
    window.attributes('-topmost', True)

    # Symbol
    ttk.Label(window, text="Symbol").pack()
    symbol_entry = ttk.Entry(window)
    symbol_entry.insert(0, "GBPUSD")
    symbol_entry.pack()

    # Entry Price
    ttk.Label(window, text="Entry Price").pack()
    entry_entry = ttk.Entry(window)
    entry_entry.pack()

    # Stop Loss
    ttk.Label(window, text="Stop Loss").pack()
    sl_entry = ttk.Entry(window)
    sl_entry.pack()

    # Take Profit (Optional)
    ttk.Label(window, text="Take Profit (Optional)").pack()
    tp_entry = ttk.Entry(window)
    tp_entry.pack()

    # Order Type
    ttk.Label(window, text="Order Type").pack()
    order_type = ttk.Combobox(window, values=["market_buy", "market_sell", "buy_stop", "sell_stop"])
    order_type.current(0)
    order_type.pack()

    # Risk Percentage
    ttk.Label(window, text="Risk % (Default: 1%)").pack()
    risk_entry = ttk.Entry(window)
    risk_entry.insert(0, "1")
    risk_entry.pack()

    # Manual Lot Size (optional override)
    ttk.Label(window, text="Manual Lot Size (Optional Override)").pack()
    lot_entry = ttk.Entry(window)
    lot_entry.pack()

    def send_order():
        symbol = symbol_entry.get().strip().upper()
        try:
            entry = float(entry_entry.get())
            sl = float(sl_entry.get())
            tp_text = tp_entry.get().strip()
            tp = float(tp_text) if tp_text else 0.0

            risk_text = risk_entry.get().strip()
            risk = float(risk_text) if risk_text else 1.0

            manual_lot_text = lot_entry.get().strip()
            manual_lot = float(manual_lot_text) if manual_lot_text else None

            type_selected = order_type.get()

            # Add pip value fallback
            pip_value = symbols_pip_values.get(symbol, 10)

            # Updated place trade function call with new inputs
            place_trade_for_all_accounts(symbol, entry, sl, tp, type_selected, pip_value, risk, manual_lot)
        except ValueError:
            print("Invalid number format.")

    ttk.Button(window, text="Send Trade", command=send_order).pack(pady=10)
    def market_buy_now():
            symbol = symbol_entry.get().strip().upper()
            sl_text = sl_entry.get().strip()
            tp_text = tp_entry.get().strip()
            risk_text = risk_entry.get().strip()
            lot_text = lot_entry.get().strip()

            try:
                sl = float(sl_text) if sl_text else 0.0
                tp = float(tp_text) if tp_text else 0.0
                risk = float(risk_text) if risk_text else 1.0
                manual_lot = float(lot_text) if lot_text else None
                pip_value = symbols_pip_values.get(symbol, 10)

                if not mt5.initialize():
                    print("❌ Failed to initialize MT5")
                    return

                if not mt5.symbol_select(symbol, True):
                    print(f"❌ Failed to select symbol {symbol}")
                    mt5.shutdown()
                    return

                tick = mt5.symbol_info_tick(symbol)
                if tick is None:
                    print(f"❌ Failed to get price tick for {symbol}")
                    mt5.shutdown()
                    return

                entry = tick.ask
                place_trade_for_all_accounts(symbol, entry, sl, tp, "market_buy", pip_value, risk, manual_lot)
                mt5.shutdown()

            except ValueError:
                print("❌ Invalid input in Market Buy Now fields.")


    def market_sell_now():
            symbol = symbol_entry.get().strip().upper()
            sl_text = sl_entry.get().strip()
            tp_text = tp_entry.get().strip()
            risk_text = risk_entry.get().strip()
            lot_text = lot_entry.get().strip()

            try:
                sl = float(sl_text) if sl_text else 0.0
                tp = float(tp_text) if tp_text else 0.0
                risk = float(risk_text) if risk_text else 1.0
                manual_lot = float(lot_text) if lot_text else None
                pip_value = symbols_pip_values.get(symbol, 10)

                if not mt5.initialize():
                    print("❌ Failed to initialize MT5")
                    return

                if not mt5.symbol_select(symbol, True):
                    print(f"❌ Failed to select symbol {symbol}")
                    mt5.shutdown()
                    return

                tick = mt5.symbol_info_tick(symbol)
                if tick is None:
                    print(f"❌ Failed to get price tick for {symbol}")
                    mt5.shutdown()
                    return

                entry = tick.bid
                place_trade_for_all_accounts(symbol, entry, sl, tp, "market_sell", pip_value, risk, manual_lot)
                mt5.shutdown()

            except ValueError:
                print("❌ Invalid input in Market Sell Now fields.")


    ttk.Button(window, text="Market Buy Now ✅", command=market_buy_now).pack(pady=5)
    ttk.Button(window, text="Market Sell Now 🔻", command=market_sell_now).pack(pady=5)


    window.mainloop()

launch_ui()
# here is my code can you add the buttons 