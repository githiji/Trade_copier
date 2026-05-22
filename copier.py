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
from tkinter import messagebox


# Ensure current dir is in path for local imports to work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


APP_ICON = "trade_copier.ico"


symbols_pip_values = {'XAUUSD':1, 'GBPUSD':10}
trailing_running = False

# === Your accounts ===
def get_enabled_accounts():
    return get_accounts_for_copier(enabled_only=True)

def resource_path(relative_path):
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

def set_window_icon(window):
    icon_path = resource_path(APP_ICON)
    if os.path.exists(icon_path):
        try:
            window.iconbitmap(icon_path)
        except tk.TclError:
            pass

def open_account_manager():
    if getattr(sys, "frozen", False):
        subprocess.Popen([sys.executable, "--accounts"])
    else:
        subprocess.Popen([sys.executable, os.path.abspath(__file__), "--accounts"])

def launch_account_manager():
    from gui import AccountManager

    window = tk.Tk()
    set_window_icon(window)
    AccountManager(window)
    window.mainloop()
    

def get_broker_symbol(base_symbol):
    symbols = mt5.symbols_get()
    
    for s in symbols:
        if s.name.startswith(base_symbol):
            return s.name  # e.g. GBPUSD.qtr

    return None

# === Utility functions ===
def calculate_lot(balance, entry_price, sl_price, risk_percent=1, pip_value_per_lot=10):
    point = 0.01 if entry_price > 100 else 0.0001
    stop_loss_pips = abs(entry_price - sl_price) / point
    risk_amount = balance * (risk_percent / 100)
    lot = risk_amount / (stop_loss_pips * pip_value_per_lot)
    return round(lot, 2)

def get_pip_size(price):
    return 0.01 if price > 100 else 0.0001

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

        if manual_lot is not None:
            lot = manual_lot
       
        else:
            lot = calculate_lot(acc_info.balance, entry, sl, risk_percent=risk_percent, pip_value_per_lot=pip_value)

        print(f"Account: {acc['login']}, Balance: {acc_info.balance}, Lot: {lot}")
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
            "magic": 10001,
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
                    "magic": 10001,
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
                    "magic": 10001,
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

def launch_floating_panel():
    window = tk.Tk()
    window.title("⚡")
    set_window_icon(window)
    window.geometry("220x315")
    window.configure(bg="#1e1e1e")
    window.attributes("-topmost", True)
    window.overrideredirect(True)  # 🔥 removes title bar

    # === DRAGGING FUNCTION ===
    def start_move(event):
        window.x = event.x
        window.y = event.y

    def stop_move(event):
        window.x = None
        window.y = None

    def on_motion(event):
        x = event.x_root - window.x
        y = event.y_root - window.y
        window.geometry(f"+{x}+{y}")

    window.bind("<Button-1>", start_move)
    window.bind("<ButtonRelease-1>", stop_move)
    window.bind("<B1-Motion>", on_motion)

    main = tk.Frame(window, bg="#1e1e1e")
    main.pack(fill="both", expand=True, padx=8, pady=8)

    # === INPUTS (MINIMAL)
    symbol_entry = tk.Entry(main, justify="center")
    symbol_entry.insert(0, "GBPUSD")
    symbol_entry.pack(fill="x", pady=3)

    sl_entry = tk.Entry(main, justify="center")
    sl_entry.insert(0, "SL")
    sl_entry.pack(fill="x", pady=3)

    tp_entry = tk.Entry(main, justify="center")
    tp_entry.insert(0, "TP")
    tp_entry.pack(fill="x", pady=3)

    lot_entry = tk.Entry(main, justify="center")
    lot_entry.insert(0, "Lot")
    lot_entry.pack(fill="x", pady=3)

    trail_entry = tk.Entry(main, justify="center")
    trail_entry.insert(0, "Trail SL")
    trail_entry.pack(fill="x", pady=3)

    # === HELPERS
    def get_inputs():
        symbol = symbol_entry.get().strip().upper()
        sl = float(sl_entry.get() or 0)
        tp = float(tp_entry.get() or 0)
        lot = float(lot_entry.get() or 0) or None
        pip_value = symbols_pip_values.get(symbol, 10)
        return symbol, sl, tp, lot, pip_value

    # === BUY
    def buy():
        try:
            symbol, sl, tp, lot, pip_value = get_inputs()

            if not mt5.initialize():
                return

            broker_symbol = get_broker_symbol(symbol)
            if not broker_symbol:
                mt5.shutdown()
                return

            mt5.symbol_select(broker_symbol, True)
            tick = mt5.symbol_info_tick(broker_symbol)

            if not tick:
                mt5.shutdown()
                return

            entry = tick.ask

            threading.Thread(
                target=place_trade_for_all_accounts,
                args=(symbol, entry, sl, tp, "market_buy", pip_value, 1, lot),
                daemon=True
            ).start()

            mt5.shutdown()

        except Exception as e:
            print("Buy error:", e)

    # === SELL
    def sell():
        try:
            symbol, sl, tp, lot, pip_value = get_inputs()

            if not mt5.initialize():
                return

            broker_symbol = get_broker_symbol(symbol)
            if not broker_symbol:
                mt5.shutdown()
                return

            mt5.symbol_select(broker_symbol, True)
            tick = mt5.symbol_info_tick(broker_symbol)

            if not tick:
                mt5.shutdown()
                return

            entry = tick.bid

            threading.Thread(
                target=place_trade_for_all_accounts,
                args=(symbol, entry, sl, tp, "market_sell", pip_value, 1, lot),
                daemon=True
            ).start()

            mt5.shutdown()

        except Exception as e:
            print("Sell error:", e)

    def set_trail_sl():
        try:
            sl_price = float(trail_entry.get() or 0)
        except ValueError:
            print("Enter a valid Trail SL price.")
            return

        symbol = symbol_entry.get().strip().upper()
        threading.Thread(
            target=set_stop_loss_price_for_all_accounts,
            args=(sl_price, symbol),
            daemon=True
        ).start()

    # === BUTTON ROW (BIG)
    trade_row = tk.Frame(main, bg="#1e1e1e")
    trade_row.pack(fill="x", pady=5)

    tk.Button(trade_row, text="BUY", bg="#00aa55", fg="white",
              command=buy, height=2).pack(side="left", expand=True, fill="x", padx=2)

    tk.Button(trade_row, text="SELL", bg="#cc3333", fg="white",
              command=sell, height=2).pack(side="right", expand=True, fill="x", padx=2)

    # === ACTION ROW
    action_row = tk.Frame(main, bg="#1e1e1e")
    action_row.pack(fill="x", pady=5)

    tk.Button(action_row, text="BE",
              command=lambda: threading.Thread(target=move_to_breakeven, daemon=True).start()
              ).pack(side="left", expand=True, fill="x", padx=2)

    tk.Button(action_row, text="Partial",
              command=lambda: threading.Thread(target=close_partial, args=(50,), daemon=True).start()
              ).pack(side="right", expand=True, fill="x", padx=2)

    trail_row = tk.Frame(main, bg="#1e1e1e")
    trail_row.pack(fill="x", pady=5)

    tk.Button(trail_row, text="Set Trail SL",
              command=set_trail_sl
              ).pack(fill="x", padx=2)

    # === CLOSE ALL
    tk.Button(main, text="Close All ❌",
              command=lambda: threading.Thread(target=close_all_positions, daemon=True).start()
              ).pack(fill="x", pady=5)

    # === EXIT BUTTON (top-right)
    close_btn = tk.Button(window, text="X", bg="#222", fg="white", command=window.destroy)
    close_btn.place(x=200, y=0)

    window.mainloop()

def launch_ui():
    window = tk.Tk()
    window.title("Trade Copier")
    set_window_icon(window)
    window.geometry("320x550")
    window.configure(bg="#1e1e1e")
    window.attributes('-topmost', True)

    main = ttk.Frame(window, padding=8)
    main.pack(fill="both", expand=True)

    # === INPUT HELPER ===
    def create_entry(label, default=""):
        frame = ttk.Frame(main)
        frame.pack(fill="x", pady=2)

        ttk.Label(frame, text=label, width=18).pack(side="left")
        e = ttk.Entry(frame)
        e.insert(0, default)
        e.pack(side="right", fill="x", expand=True)
        return e

    symbol_entry = create_entry("Symbol", "GBPUSD")
    entry_entry = create_entry("Entry")
    sl_entry = create_entry("SL")
    tp_entry = create_entry("TP")
    risk_entry = create_entry("Risk %", "1")
    lot_entry = create_entry("Lot (opt)")
    profit_entry = create_entry("Target Profit")
    loss_entry = create_entry("Max Loss")
    partial_entry = create_entry("Partial %")
    trail_entry = create_entry("Trail SL Price")

    ttk.Button(main, text="Accounts", command=open_account_manager).pack(fill="x", pady=(4, 5))

    # === ORDER TYPE ===
    order_type = ttk.Combobox(
        main,
        values=["market_buy", "market_sell", "buy_stop", "sell_stop"],
        height=4
    )
    order_type.current(0)
    order_type.pack(fill="x", pady=5)

    # === PnL ===
    pnl_label = tk.Label(
        main,
        text="PnL: 0.00",
        font=("Segoe UI", 11, "bold"),
        bg="#1e1e1e"
    )
    pnl_label.pack(pady=5)

    def update_pnl():
        total = get_total_profit()
        pnl_label.config(
            text=f"PnL: {round(total,2)}",
            fg="#00ff88" if total >= 0 else "#ff4d4d"
        )
        window.after(2000, update_pnl)

    update_pnl()

    # === INPUT PARSER ===
    def get_inputs():
        symbol = symbol_entry.get().strip().upper()
        sl = float(sl_entry.get() or 0)
        tp = float(tp_entry.get() or 0)
        risk = float(risk_entry.get() or 1)
        lot = float(lot_entry.get() or 0) or None
        pip_value = symbols_pip_values.get(symbol, 10)
        return symbol, sl, tp, risk, lot, pip_value

    # === BUY / SELL ROW (🔥 KEY IMPROVEMENT)
    trade_row = ttk.Frame(main)
    trade_row.pack(fill="x", pady=5)

    def market_buy():
        try:
            symbol, sl, tp, risk, lot, pip_value = get_inputs()

            if not mt5.initialize():
                return

            broker_symbol = get_broker_symbol(symbol)
            if not broker_symbol:
                mt5.shutdown()
                return

            mt5.symbol_select(broker_symbol, True)
            tick = mt5.symbol_info_tick(broker_symbol)
            if not tick:
                mt5.shutdown()
                return

            entry = tick.ask

            threading.Thread(
                target=place_trade_for_all_accounts,
                args=(symbol, entry, sl, tp, "market_buy", pip_value, risk, lot),
                daemon=True
            ).start()

            mt5.shutdown()

        except:
            print("Buy error")

    def market_sell():
        try:
            symbol, sl, tp, risk, lot, pip_value = get_inputs()

            if not mt5.initialize():
                return

            broker_symbol = get_broker_symbol(symbol)
            if not broker_symbol:
                mt5.shutdown()
                return

            mt5.symbol_select(broker_symbol, True)
            tick = mt5.symbol_info_tick(broker_symbol)
            if not tick:
                mt5.shutdown()
                return

            entry = tick.bid

            threading.Thread(
                target=place_trade_for_all_accounts,
                args=(symbol, entry, sl, tp, "market_sell", pip_value, risk, lot),
                daemon=True
            ).start()

            mt5.shutdown()

        except:
            print("Sell error")

    # 🔥 SIDE-BY-SIDE BUTTONS
    tk.Button(trade_row, text="BUY", bg="#00aa55", fg="white",
              command=market_buy, height=2).pack(side="left", expand=True, fill="x", padx=2)

    tk.Button(trade_row, text="SELL", bg="#cc3333", fg="white",
              command=market_sell, height=2).pack(side="right", expand=True, fill="x", padx=2)

    def set_trail_sl():
        try:
            sl_price = float(trail_entry.get() or 0)
        except ValueError:
            print("Enter a valid Trail SL price.")
            return

        symbol = symbol_entry.get().strip().upper()
        threading.Thread(
            target=set_stop_loss_price_for_all_accounts,
            args=(sl_price, symbol),
            daemon=True
        ).start()

    # === ACTION ROWS (grouped)
    row1 = ttk.Frame(main)
    row1.pack(fill="x", pady=3)

    ttk.Button(row1, text="Partial ✂️",
               command=lambda: threading.Thread(
                   target=close_partial,
                   args=(float(partial_entry.get() or 0),),
                   daemon=True).start()
               ).pack(side="left", expand=True, fill="x", padx=2)

    ttk.Button(row1, text="BE ⚖️",
               command=lambda: threading.Thread(
                   target=move_to_breakeven,
                   daemon=True).start()
               ).pack(side="right", expand=True, fill="x", padx=2)

    row2 = ttk.Frame(main)
    row2.pack(fill="x", pady=3)

    ttk.Button(row2, text="Auto Close 🧠",
               command=lambda: threading.Thread(
                   target=monitor_profit_loss,
                   args=(float(profit_entry.get() or 0), float(loss_entry.get() or 0)),
                   daemon=True).start()
               ).pack(side="left", expand=True, fill="x", padx=2)

    ttk.Button(row2, text="Stop 🛑",
               command=stop_auto_close
               ).pack(side="right", expand=True, fill="x", padx=2)

    row3 = ttk.Frame(main)
    row3.pack(fill="x", pady=3)

    ttk.Button(row3, text="Set Trail SL",
               command=set_trail_sl
               ).pack(fill="x", padx=2)

    # === FINAL BUTTON
    ttk.Button(main, text="Close All ❌",
               command=lambda: threading.Thread(
                   target=close_all_positions,
                   daemon=True).start()
               ).pack(fill="x", pady=8)

    window.mainloop()

if __name__ == "__main__":
    if "--accounts" in sys.argv:
        launch_account_manager()
    else:
        threading.Thread(target=launch_ui, daemon=True).start()
        launch_floating_panel()
