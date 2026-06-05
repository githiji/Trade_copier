import os
import sys
import sqlite3
import threading
import tkinter as tk
import MetaTrader5 as mt5

from copier import  open_account_manager, get_total_profit, monitor_profit_loss, stop_auto_close, close_all_positions,place_trade_for_all_accounts, set_stop_loss_price_for_all_accounts, close_partial, move_to_breakeven

from tkinter import ttk, messagebox
from risk_manager import get_broker_symbol, calculate_lot, get_pip_size, calculate_risk_reward_ratio, get_deal_pnl, is_closed_copier_deal, get_risk_tracker, apply_trade_result_to_tracker, update_risk_tracker_from_history, get_managed_risk_percent, COPIER_MAGIC, risk_trackers, risk_tracker_lock, REDUCED_RISK_PERCENT 


sys.path.append(os.path.dirname(os.path.abspath(__file__)))
symbols_pip_values = {'XAUUSD':1, 'GBPUSD':10}
FONT = ("Segoe UI", 10)
FONT_SMALL = ("Segoe UI", 9)
FONT_HEADER = ("Segoe UI Semibold", 13)
COLORS = {
    "bg": "#101418",
    "panel": "#171c22",
    "panel_alt": "#1f2630",
    "field": "#0f141a",
    "border": "#2d3743",
    "text": "#eef3f8",
    "muted": "#97a4b3",
    "accent": "#4f8cff",
    "accent_hover": "#6aa0ff",
    "buy": "#16a36a",
    "buy_hover": "#1fbd7c",
    "sell": "#d84a55",
    "sell_hover": "#ef5f6b",
    "danger": "#b93d48",
    "danger_hover": "#d9505d",
}

APP_ICON = "trade_copier.ico"

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

def configure_dark_theme(window):
    window.configure(bg=COLORS["bg"])
    style = ttk.Style(window)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure(".", font=FONT)
    style.configure("TFrame", background=COLORS["bg"])
    style.configure("Panel.TFrame", background=COLORS["panel"], borderwidth=0)
    style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["text"])
    style.configure("Muted.TLabel", background=COLORS["bg"], foreground=COLORS["muted"], font=FONT_SMALL)
    style.configure("Header.TLabel", background=COLORS["bg"], foreground=COLORS["text"], font=FONT_HEADER)
    style.configure(
        "TEntry",
        fieldbackground=COLORS["field"],
        background=COLORS["field"],
        foreground=COLORS["text"],
        insertcolor=COLORS["text"],
        bordercolor=COLORS["border"],
        lightcolor=COLORS["border"],
        darkcolor=COLORS["border"],
        padding=(8, 6),
        relief="flat",
    )
    style.configure(
        "TCombobox",
        fieldbackground=COLORS["field"],
        background=COLORS["panel_alt"],
        foreground=COLORS["text"],
        arrowcolor=COLORS["text"],
        bordercolor=COLORS["border"],
        lightcolor=COLORS["border"],
        darkcolor=COLORS["border"],
        padding=(8, 6),
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", COLORS["field"])],
        foreground=[("readonly", COLORS["text"])],
        selectbackground=[("readonly", COLORS["field"])],
        selectforeground=[("readonly", COLORS["text"])],
    )
    style.configure(
        "TButton",
        background=COLORS["panel_alt"],
        foreground=COLORS["text"],
        borderwidth=0,
        focusthickness=0,
        padding=(10, 8),
        relief="flat",
    )
    style.map(
        "TButton",
        background=[("active", COLORS["border"]), ("pressed", COLORS["border"])],
        foreground=[("disabled", COLORS["muted"])],
    )
    style.configure("Accent.TButton", background=COLORS["accent"], foreground="white")
    style.map("Accent.TButton", background=[("active", COLORS["accent_hover"]), ("pressed", COLORS["accent"])])


def dark_entry(parent, justify="left"):
    entry = tk.Entry(
        parent,
        justify=justify,
        bg=COLORS["field"],
        fg=COLORS["text"],
        insertbackground=COLORS["text"],
        relief="flat",
        bd=0,
        highlightthickness=1,
        highlightbackground=COLORS["border"],
        highlightcolor=COLORS["accent"],
        font=FONT,
    )
    return entry



def launch_account_manager():
    from accounts import AccountManager

    window = tk.Tk()
    set_window_icon(window)
    AccountManager(window)
    window.mainloop()

def action_button(parent, text, command, bg=None, hover=None, fg="white", height=2):
    bg = bg or COLORS["panel_alt"]
    hover = hover or COLORS["border"]
    button = tk.Button(
        parent,
        text=text,
        command=command,
        bg=bg,
        fg=fg,
        activebackground=hover,
        activeforeground=fg,
        relief="flat",
        bd=0,
        height=height,
        cursor="hand2",
        font=("Segoe UI Semibold", 10),
        padx=10,
        pady=6,
    )
    button.bind("<Enter>", lambda _event: button.configure(bg=hover))
    button.bind("<Leave>", lambda _event: button.configure(bg=bg))
    return button


def launch_floating_panel():
    window = tk.Tk()
    window.title("Trade Copier Quick Panel")
    set_window_icon(window)
    window.geometry("280x440")
    configure_dark_theme(window)
    window.attributes("-topmost", True)
    window.overrideredirect(True)

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

    shell = tk.Frame(window, bg=COLORS["panel"], highlightthickness=1, highlightbackground=COLORS["border"])
    shell.pack(fill="both", expand=True, padx=6, pady=6)

    header = tk.Frame(shell, bg=COLORS["panel"])
    header.pack(fill="x", padx=10, pady=(8, 4))

    tk.Label(
        header,
        text="Quick Trade",
        bg=COLORS["panel"],
        fg=COLORS["text"],
        font=("Segoe UI Semibold", 10),
    ).pack(side="left")

    close_btn = action_button(header, "X", window.destroy, bg=COLORS["panel_alt"], hover=COLORS["danger"], height=1)
    close_btn.pack(side="right", ipadx=4, ipady=0)

    main = tk.Frame(shell, bg=COLORS["panel"])
    main.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    inputs = tk.Frame(main, bg=COLORS["panel"])
    inputs.pack(fill="x")
    inputs.columnconfigure(0, weight=1)
    inputs.columnconfigure(1, weight=1)

    def create_quick_entry(row, column, label, default=""):
        cell = tk.Frame(inputs, bg=COLORS["panel"])
        cell.grid(row=row, column=column, sticky="ew", padx=(0, 4) if column == 0 else (4, 0), pady=3)
        tk.Label(cell, text=label, bg=COLORS["panel"], fg=COLORS["muted"], font=FONT_SMALL).pack(anchor="w")
        entry = dark_entry(cell, justify="center")
        entry.insert(0, default)
        entry.pack(fill="x", ipady=5)
        return entry

    symbol_entry = create_quick_entry(0, 0, "Symbol", "GBPUSD")
    lot_entry = create_quick_entry(0, 1, "Lot")
    sl_entry = create_quick_entry(1, 0, "SL")
    tp_entry = create_quick_entry(1, 1, "TP")
    trail_entry = create_quick_entry(2, 0, "Trail SL")
    partial_entry = create_quick_entry(2, 1, "Partial %", "50")

    # === HELPERS
    def read_float(entry, default=0):
        value = entry.get().strip()
        if not value:
            return default
        try:
            return float(value)
        except ValueError:
            return default

    def get_inputs():
        symbol = symbol_entry.get().strip().upper()
        sl = read_float(sl_entry, 0)
        tp = read_float(tp_entry, 0)
        lot = read_float(lot_entry, 0) or None
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
        sl_price = read_float(trail_entry, 0)
        if sl_price <= 0:
            print("Enter a valid Trail SL price.")
            return

        symbol = symbol_entry.get().strip().upper()
        threading.Thread(
            target=set_stop_loss_price_for_all_accounts,
            args=(sl_price, symbol),
            daemon=True
        ).start()

    # === BUTTON ROW (BIG)
    trade_row = tk.Frame(main, bg=COLORS["panel"])
    trade_row.pack(fill="x", pady=(8, 5))

    action_button(trade_row, "BUY", buy, bg=COLORS["buy"], hover=COLORS["buy_hover"]).pack(
        side="left", expand=True, fill="x", padx=(0, 3)
    )

    action_button(trade_row, "SELL", sell, bg=COLORS["sell"], hover=COLORS["sell_hover"]).pack(
        side="right", expand=True, fill="x", padx=(3, 0)
    )

    # === ACTION ROW
    trail_row = tk.Frame(main, bg=COLORS["panel"])
    trail_row.pack(fill="x", pady=4)

    action_button(
        trail_row,
        "Set Trail SL",
        set_trail_sl,
        bg=COLORS["panel_alt"],
    ).pack(fill="x")

    action_row = tk.Frame(main, bg=COLORS["panel"])
    action_row.pack(fill="x", pady=4)

    action_button(
        action_row,
        "Partial Close",
        lambda: threading.Thread(target=close_partial, args=(read_float(partial_entry, 50),), daemon=True).start(),
        bg=COLORS["panel_alt"],
    ).pack(side="left", expand=True, fill="x", padx=(0, 3))

    action_button(
        action_row,
        "Breakeven",
        lambda: threading.Thread(target=move_to_breakeven, daemon=True).start(),
        bg=COLORS["panel_alt"],
    ).pack(side="right", expand=True, fill="x", padx=(3, 0))

    # === CLOSE ALL
    action_button(
        main,
        "Close All",
        lambda: threading.Thread(target=close_all_positions, daemon=True).start(),
        bg=COLORS["danger"],
        hover=COLORS["danger_hover"],
    ).pack(fill="x", pady=(7, 0))

    window.mainloop()

  
def launch_ui():
    window = tk.Tk()
    window.title("Trade Copier")
    set_window_icon(window)
    window.geometry("420x360")
    window.minsize(380, 320)
    configure_dark_theme(window)
    window.attributes('-topmost', True)

    main = ttk.Frame(window, padding=14)
    main.pack(fill="both", expand=True)

    header = ttk.Frame(main)
    header.pack(fill="x", pady=(0, 12))

    ttk.Label(header, text="Trade Copier", style="Header.TLabel").pack(side="left")
    ttk.Button(
        header,
        text="Accounts",
        style="Accent.TButton",
        command=open_account_manager
    ).pack(side="right")

    # === PnL ===
    status_panel = ttk.Frame(main, style="Panel.TFrame", padding=12)
    status_panel.pack(fill="x", pady=(0, 10))

    ttk.Label(
        status_panel,
        text="Live account profit/loss",
        background=COLORS["panel"],
        foreground=COLORS["muted"],
    ).pack(anchor="w")

    pnl_label = tk.Label(
        status_panel,
        text="PnL: 0.00",
        font=("Segoe UI Semibold", 24),
        bg=COLORS["panel"],
        fg=COLORS["text"]
    )
    pnl_label.pack(anchor="w", pady=(4, 0))

    def update_pnl():
        total = get_total_profit()
        pnl_label.config(
            text=f"PnL: {round(total, 2)}",
            fg="#00ff88" if total >= 0 else "#ff4d4d"
        )
        window.after(2000, update_pnl)

    update_pnl()

    auto_panel = ttk.Frame(main, style="Panel.TFrame", padding=12)
    auto_panel.pack(fill="x", pady=(0, 10))
    auto_panel.columnconfigure(0, weight=1)
    auto_panel.columnconfigure(1, weight=1)

    ttk.Label(
        auto_panel,
        text="Auto Close",
        style="Header.TLabel",
        background=COLORS["panel"]
    ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

    def create_auto_entry(row, column, label):
        frame = ttk.Frame(auto_panel, style="Panel.TFrame")
        frame.grid(
            row=row,
            column=column,
            sticky="ew",
            padx=(0, 5) if column == 0 else (5, 0),
            pady=(0, 8)
        )

        frame.columnconfigure(0, weight=1)

        ttk.Label(
            frame,
            text=label,
            background=COLORS["panel"],
            foreground=COLORS["muted"]
        ).grid(row=0, column=0, sticky="w", pady=(0, 2))

        entry = ttk.Entry(frame)
        entry.grid(row=1, column=0, sticky="ew")

        return entry

    profit_entry = create_auto_entry(1, 0, "Target Profit")
    loss_entry = create_auto_entry(1, 1, "Max Loss")

    def close_all_now():
        confirm = messagebox.askyesno(
            "Confirm Close All",
            "Are you sure you want to close ALL trades on ALL accounts?"
        )

        if confirm:
            threading.Thread(
                target=close_all_positions,
                daemon=True
            ).start()

    # === CLOSE ALL BUTTON ===
    action_button(
        main,
        "❌ CLOSE ALL",
        close_all_now,
        bg=COLORS["danger"],
        hover=COLORS["danger_hover"]
    ).pack(fill="x", pady=(0, 10))

    def read_float(entry, default=0):
        value = entry.get().strip()

        if not value:
            return default

        try:
            return float(value)
        except ValueError:
            return default

    auto_row = tk.Frame(auto_panel, bg=COLORS["panel"])
    auto_row.grid(row=2, column=0, columnspan=2, sticky="ew")

    action_button(
        auto_row,
        "Start Auto Close",
        lambda: threading.Thread(
            target=monitor_profit_loss,
            args=(
                read_float(profit_entry, 0),
                read_float(loss_entry, 0)
            ),
            daemon=True,
        ).start(),
        bg=COLORS["panel_alt"],
    ).pack(side="left", expand=True, fill="x", padx=(0, 4))

    action_button(
        auto_row,
        "Stop Auto Close",
        stop_auto_close,
        bg=COLORS["panel_alt"],
    ).pack(side="right", expand=True, fill="x", padx=(4, 0))

    ttk.Label(
        main,
        text="Use Quick Trade for BUY, SELL, Trail SL, Partial Close, Breakeven, and Close All.",
        style="Muted.TLabel",
        wraplength=360,
        justify="left",
    ).pack(fill="x")

    window.mainloop()
  

  
