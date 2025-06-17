import tkinter as tk
from tkinter import ttk
import MetaTrader5 as mt5

# === Your accounts ===
accounts = [
    {
        "login": 5037217440,
        "password": "2002bkg@A",
        "server": "MetaQuotes-Demo",
        "path": "C:\\Program Files\\MetaTrader 5\\terminal64.exe",
        'cfd_symbol': "us100",
        'pip_value':0.1 
    },
    # Add more if needed
]

# === Utility functions ===
def calculate_lot(balance, entry_price, sl_price, risk_percent=1, pip_value_per_lot=1):
    point = 0.01 if entry_price > 100 else 0.0001
    stop_loss_pips = abs(entry_price - sl_price) / point
    risk_amount = balance * (risk_percent / 100)
    lot = risk_amount / (stop_loss_pips * pip_value_per_lot)
    return round(lot, 2)

def place_trade_for_all_accounts(symbol, entry, sl, tp, order_type):
    for acc in accounts:
        print(f"Connecting to account {acc['login']}...")
        if not mt5.initialize(path=acc['path'], login=acc['login'], password=acc['password'], server=acc['server']):
            print(f"Connection failed: {mt5.last_error()}")
            continue

        acc_info = mt5.account_info()
        if acc_info is None:
            print("Failed to get account info")
            mt5.shutdown()
            continue

        lot = calculate_lot(acc_info.balance, entry, sl)
        print(f"Account: {acc['login']}, Balance: {acc_info.balance}, Lot: {lot}")

        request = {
            "action": mt5.TRADE_ACTION_DEAL if "market" in order_type else mt5.TRADE_ACTION_PENDING,
            "symbol": acc['cfd_symbol'] or symbol,
            "volume": lot,
            "type": {
                "market_buy": mt5.ORDER_TYPE_BUY,
                "market_sell": mt5.ORDER_TYPE_SELL,
                "buy_stop": mt5.ORDER_TYPE_BUY_STOP,
                "sell_stop": mt5.ORDER_TYPE_SELL_STOP,
            }[order_type],
            "price": entry if "stop" in order_type else mt5.symbol_info_tick(symbol).ask if "buy" in order_type else mt5.symbol_info_tick(symbol).bid,
            "sl": sl,
            "tp": tp,
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
    window.geometry("240x280")
    window.attributes('-topmost', True)  # Always on top

    ttk.Label(window, text="Symbol").pack()
    symbol_entry = ttk.Entry(window)
    symbol_entry.insert(0, "XAUUSD")
    symbol_entry.pack()

    ttk.Label(window, text="Entry Price").pack()
    entry_entry = ttk.Entry(window)
    entry_entry.pack()

    ttk.Label(window, text="Stop Loss").pack()
    sl_entry = ttk.Entry(window)
    sl_entry.pack()

    ttk.Label(window, text="Take Profit").pack()
    tp_entry = ttk.Entry(window)
    tp_entry.pack()

    ttk.Label(window, text="Order Type").pack()
    order_type = ttk.Combobox(window, values=["market_buy", "market_sell", "buy_stop", "sell_stop"])
    order_type.current(2)
    order_type.pack()

    def send_order():
        symbol = symbol_entry.get()
        try:
            entry = float(entry_entry.get())
            sl = float(sl_entry.get())
            tp = float(tp_entry.get())
            type_selected = order_type.get()
            place_trade_for_all_accounts(symbol, entry, sl, tp, type_selected)
        except ValueError:
            print("Invalid number format.")

    ttk.Button(window, text="Send Trade", command=send_order).pack(pady=10)
    window.mainloop()

launch_ui()
