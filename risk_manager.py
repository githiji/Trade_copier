import MetaTrader5 as mt5
from datetime import datetime
import threading

symbols_pip_values = {'XAUUSD':1, 'GBPUSD':10}
trailing_running = False
COPIER_MAGIC = 10001
MIN_RISK_REWARD_RATIO = 1.5
REDUCED_RISK_PERCENT = 0.5
LOSS_STREAK_LIMIT = 3
RISK_TRACKER_STARTED_AT = datetime.now()
risk_trackers = {}
risk_tracker_lock = threading.Lock()



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

def calculate_risk_reward_ratio(entry_price, sl_price, tp_price, order_type):
    if entry_price <= 0 or sl_price <= 0 or tp_price <= 0:
        return None

    if "buy" in order_type:
        risk = entry_price - sl_price
        reward = tp_price - entry_price
    else:
        risk = sl_price - entry_price
        reward = entry_price - tp_price

    if risk <= 0 or reward <= 0:
        return None

    return reward / risk


def get_trade_validation_error(entry_price, sl_price, tp_price, order_type, min_rr=MIN_RISK_REWARD_RATIO):
    if entry_price <= 0:
        return "Entry price is missing."
    if sl_price <= 0:
        return "Enter a stop loss price."
    if tp_price <= 0:
        return "Enter a take profit price."

    if "buy" in order_type:
        if sl_price >= entry_price:
            return f"For BUY, SL ({sl_price}) must be below entry ({entry_price})."
        if tp_price <= entry_price:
            return f"For BUY, TP ({tp_price}) must be above entry ({entry_price})."
    else:
        if sl_price <= entry_price:
            return f"For SELL, SL ({sl_price}) must be above entry ({entry_price})."
        if tp_price >= entry_price:
            return f"For SELL, TP ({tp_price}) must be below entry ({entry_price})."

    rr_ratio = calculate_risk_reward_ratio(entry_price, sl_price, tp_price, order_type)
    if rr_ratio is None:
        return "SL/TP do not create a valid risk/reward setup."
    if rr_ratio < min_rr:
        return (
            f"RR {rr_ratio:.2f} is below required 1:{min_rr}. "
            "Move TP farther away or SL closer to entry."
        )

    return None


def get_deal_pnl(deal):
    return (
        float(getattr(deal, "profit", 0) or 0)
        + float(getattr(deal, "commission", 0) or 0)
        + float(getattr(deal, "swap", 0) or 0)
    )

def is_closed_copier_deal(deal):
    entry = getattr(deal, "entry", None)
    close_entries = {mt5.DEAL_ENTRY_OUT}
    if hasattr(mt5, "DEAL_ENTRY_INOUT"):
        close_entries.add(mt5.DEAL_ENTRY_INOUT)

    if entry not in close_entries:
        return False

    return getattr(deal, "magic", None) == COPIER_MAGIC

def get_risk_tracker(login):
    login = str(login)
    tracker = risk_trackers.get(login)
    if tracker is None:
        tracker = {
            "seen_deals": set(),
            "loss_streak": 0,
            "streak_loss_amount": 0.0,
            "reduced": False,
            "recovery_target": 0.0,
            "recovery_balance": 0.0,
        }
        risk_trackers[login] = tracker

    return tracker

def apply_trade_result_to_tracker(login, tracker, pnl):
    if tracker["reduced"]:
        tracker["recovery_balance"] += pnl
        if tracker["recovery_balance"] >= tracker["recovery_target"]:
            tracker["reduced"] = False
            tracker["loss_streak"] = 0
            tracker["streak_loss_amount"] = 0.0
            tracker["recovery_target"] = 0.0
            tracker["recovery_balance"] = 0.0
            print(f"Risk restored for {login}: recovered losses, using normal risk again.")
        return

    if pnl < 0:
        tracker["loss_streak"] += 1
        tracker["streak_loss_amount"] += abs(pnl)
        print(f"Loss tracked for {login}: {tracker['loss_streak']}/{LOSS_STREAK_LIMIT}.")

        if tracker["loss_streak"] >= LOSS_STREAK_LIMIT:
            tracker["reduced"] = True
            tracker["recovery_target"] = tracker["streak_loss_amount"]
            tracker["recovery_balance"] = 0.0
            print(
                f"Risk reduced for {login}: {LOSS_STREAK_LIMIT} losses tracked, "
                f"using {REDUCED_RISK_PERCENT}% until {tracker['recovery_target']:.2f} is recovered."
            )
    elif pnl > 0:
        tracker["loss_streak"] = 0
        tracker["streak_loss_amount"] = 0.0

def update_risk_tracker_from_history(login):
    to_date = datetime.now()
    from_date = RISK_TRACKER_STARTED_AT
    deals = mt5.history_deals_get(from_date, to_date)

    if deals is None:
        print(f"Could not read trade history for {login}: {mt5.last_error()}")
        return

    with risk_tracker_lock:
        tracker = get_risk_tracker(login)
        closed_deals = sorted(
            (deal for deal in deals if is_closed_copier_deal(deal)),
            key=lambda deal: (getattr(deal, "time_msc", 0), getattr(deal, "ticket", 0))
        )

        for deal in closed_deals:
            ticket = getattr(deal, "ticket", None)
            if ticket in tracker["seen_deals"]:
                continue

            tracker["seen_deals"].add(ticket)
            apply_trade_result_to_tracker(login, tracker, get_deal_pnl(deal))

def get_managed_risk_percent(login, requested_risk_percent):
    with risk_tracker_lock:
        tracker = get_risk_tracker(login)
        if tracker["reduced"]:
            return min(requested_risk_percent, REDUCED_RISK_PERCENT)

    return requested_risk_percent
