import json
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timedelta

import MetaTrader5 as mt5

from database import DB_PATH


DEFAULT_HISTORY_LOOKBACK_HOURS = 24
_db_lock = threading.Lock()


def _now_iso():
    return datetime.now().isoformat(timespec="seconds")


def _event_time_from_msc(time_msc, fallback_time=None):
    if time_msc:
        try:
            return datetime.fromtimestamp(float(time_msc) / 1000).isoformat(timespec="seconds")
        except (TypeError, ValueError, OSError):
            pass

    if fallback_time:
        try:
            return datetime.fromtimestamp(float(fallback_time)).isoformat(timespec="seconds")
        except (TypeError, ValueError, OSError):
            pass

    return _now_iso()


def _json_default(value):
    if hasattr(value, "_asdict"):
        return _to_plain_dict(value)
    if isinstance(value, set):
        return sorted(value)
    return str(value)


def _to_plain_dict(value):
    if value is None:
        return None

    if hasattr(value, "_asdict"):
        value = value._asdict()

    if isinstance(value, dict):
        return {key: _to_plain_dict(item) for key, item in value.items()}

    if isinstance(value, (list, tuple)):
        return [_to_plain_dict(item) for item in value]

    return value


def _to_json(value):
    return json.dumps(_to_plain_dict(value), default=_json_default, sort_keys=True)


def init_event_db():
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS trade_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                event_time TEXT NOT NULL,
                account_login TEXT NOT NULL,
                event_type TEXT NOT NULL,
                status TEXT,
                symbol TEXT,
                side TEXT,
                volume REAL,
                price REAL,
                sl REAL,
                tp REAL,
                order_ticket TEXT,
                deal_ticket TEXT,
                position_ticket TEXT,
                profit REAL,
                message TEXT,
                request_json TEXT,
                result_json TEXT,
                raw_json TEXT,
                source_ticket TEXT,
                UNIQUE(account_login, event_type, source_ticket)
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS event_collection_state (
                account_login TEXT PRIMARY KEY,
                last_deal_time_msc INTEGER DEFAULT 0,
                last_order_time_msc INTEGER DEFAULT 0,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
        conn.close()


def record_trade_event(
    account_login,
    event_type,
    status=None,
    symbol=None,
    side=None,
    volume=None,
    price=None,
    sl=None,
    tp=None,
    order_ticket=None,
    deal_ticket=None,
    position_ticket=None,
    profit=None,
    message=None,
    request=None,
    result=None,
    raw=None,
    source_ticket=None,
    event_time=None,
):
    init_event_db()
    source_ticket = str(source_ticket or uuid.uuid4())

    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR IGNORE INTO trade_events (
                created_at, event_time, account_login, event_type, status, symbol,
                side, volume, price, sl, tp, order_ticket, deal_ticket,
                position_ticket, profit, message, request_json, result_json,
                raw_json, source_ticket
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _now_iso(),
                event_time or _now_iso(),
                str(account_login),
                event_type,
                status,
                symbol,
                side,
                volume,
                price,
                sl,
                tp,
                str(order_ticket) if order_ticket else None,
                str(deal_ticket) if deal_ticket else None,
                str(position_ticket) if position_ticket else None,
                profit,
                message,
                _to_json(request) if request is not None else None,
                _to_json(result) if result is not None else None,
                _to_json(raw) if raw is not None else None,
                source_ticket,
            ),
        )
        conn.commit()
        conn.close()


def record_order_send_event(account_login, event_type, request, result):
    result_data = _to_plain_dict(result) or {}
    request_data = _to_plain_dict(request) or {}
    retcode = result_data.get("retcode")
    success_codes = {
        getattr(mt5, "TRADE_RETCODE_DONE", None),
        getattr(mt5, "TRADE_RETCODE_DONE_PARTIAL", None),
        getattr(mt5, "TRADE_RETCODE_PLACED", None),
    }
    status = "sent" if retcode in success_codes else "failed"

    source_ticket = (
        result_data.get("deal")
        or result_data.get("order")
        or f"{int(time.time() * 1000)}-{uuid.uuid4()}"
    )

    record_trade_event(
        account_login=account_login,
        event_type=event_type,
        status=status,
        symbol=request_data.get("symbol"),
        side=_order_type_name(request_data.get("type")),
        volume=request_data.get("volume"),
        price=result_data.get("price") or request_data.get("price"),
        sl=request_data.get("sl"),
        tp=request_data.get("tp"),
        order_ticket=result_data.get("order"),
        deal_ticket=result_data.get("deal"),
        position_ticket=request_data.get("position"),
        message=result_data.get("comment"),
        request=request,
        result=result,
        source_ticket=source_ticket,
    )


def _order_type_name(order_type):
    mapping = {
        getattr(mt5, "ORDER_TYPE_BUY", None): "buy",
        getattr(mt5, "ORDER_TYPE_SELL", None): "sell",
        getattr(mt5, "ORDER_TYPE_BUY_STOP", None): "buy_stop",
        getattr(mt5, "ORDER_TYPE_SELL_STOP", None): "sell_stop",
        getattr(mt5, "ORDER_TYPE_BUY_LIMIT", None): "buy_limit",
        getattr(mt5, "ORDER_TYPE_SELL_LIMIT", None): "sell_limit",
    }
    return mapping.get(order_type, str(order_type) if order_type is not None else None)


def _deal_side_name(deal_type):
    mapping = {
        getattr(mt5, "DEAL_TYPE_BUY", None): "buy",
        getattr(mt5, "DEAL_TYPE_SELL", None): "sell",
    }
    return mapping.get(deal_type, str(deal_type) if deal_type is not None else None)


def _deal_event_type(deal):
    entry = getattr(deal, "entry", None)
    if entry == getattr(mt5, "DEAL_ENTRY_IN", None):
        return "deal_opened"
    if entry == getattr(mt5, "DEAL_ENTRY_OUT", None):
        return "deal_closed"
    if hasattr(mt5, "DEAL_ENTRY_INOUT") and entry == mt5.DEAL_ENTRY_INOUT:
        return "deal_reversed"
    return "deal"


def _get_collection_state(account_login):
    init_event_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT last_deal_time_msc, last_order_time_msc
        FROM event_collection_state
        WHERE account_login = ?
        """,
        (str(account_login),),
    )
    row = cursor.fetchone()
    conn.close()

    if row:
        return int(row[0] or 0), int(row[1] or 0)

    return 0, 0


def _save_collection_state(account_login, last_deal_time_msc, last_order_time_msc):
    init_event_db()
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO event_collection_state (
                account_login, last_deal_time_msc, last_order_time_msc, updated_at
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(account_login) DO UPDATE SET
                last_deal_time_msc = excluded.last_deal_time_msc,
                last_order_time_msc = excluded.last_order_time_msc,
                updated_at = excluded.updated_at
            """,
            (str(account_login), last_deal_time_msc, last_order_time_msc, _now_iso()),
        )
        conn.commit()
        conn.close()


def collect_account_trade_events(account_login, lookback_hours=DEFAULT_HISTORY_LOOKBACK_HOURS):
    last_deal_msc, last_order_msc = _get_collection_state(account_login)
    last_seen_msc = max(last_deal_msc, last_order_msc)

    if last_seen_msc:
        from_date = datetime.fromtimestamp(max(last_seen_msc - 1000, 0) / 1000)
    else:
        from_date = datetime.now() - timedelta(hours=lookback_hours)

    to_date = datetime.now()
    newest_deal_msc = last_deal_msc
    newest_order_msc = last_order_msc

    deals = mt5.history_deals_get(from_date, to_date)
    if deals is not None:
        for deal in sorted(deals, key=lambda item: (getattr(item, "time_msc", 0), getattr(item, "ticket", 0))):
            time_msc = int(getattr(deal, "time_msc", 0) or 0)
            newest_deal_msc = max(newest_deal_msc, time_msc)
            record_trade_event(
                account_login=account_login,
                event_type=_deal_event_type(deal),
                status="history",
                symbol=getattr(deal, "symbol", None),
                side=_deal_side_name(getattr(deal, "type", None)),
                volume=getattr(deal, "volume", None),
                price=getattr(deal, "price", None),
                order_ticket=getattr(deal, "order", None),
                deal_ticket=getattr(deal, "ticket", None),
                position_ticket=getattr(deal, "position_id", None),
                profit=(
                    float(getattr(deal, "profit", 0) or 0)
                    + float(getattr(deal, "commission", 0) or 0)
                    + float(getattr(deal, "swap", 0) or 0)
                ),
                message=getattr(deal, "comment", None),
                raw=deal,
                source_ticket=getattr(deal, "ticket", None),
                event_time=_event_time_from_msc(time_msc, getattr(deal, "time", None)),
            )
    else:
        print(f"Could not collect deal history for {account_login}: {mt5.last_error()}")

    orders = mt5.history_orders_get(from_date, to_date)
    if orders is not None:
        for order in sorted(orders, key=lambda item: (getattr(item, "time_done_msc", 0), getattr(item, "ticket", 0))):
            time_msc = int(
                getattr(order, "time_done_msc", 0)
                or getattr(order, "time_setup_msc", 0)
                or 0
            )
            newest_order_msc = max(newest_order_msc, time_msc)
            record_trade_event(
                account_login=account_login,
                event_type="order_history",
                status=str(getattr(order, "state", None)),
                symbol=getattr(order, "symbol", None),
                side=_order_type_name(getattr(order, "type", None)),
                volume=getattr(order, "volume_initial", None),
                price=getattr(order, "price_open", None),
                sl=getattr(order, "sl", None),
                tp=getattr(order, "tp", None),
                order_ticket=getattr(order, "ticket", None),
                position_ticket=getattr(order, "position_id", None),
                message=getattr(order, "comment", None),
                raw=order,
                source_ticket=getattr(order, "ticket", None),
                event_time=_event_time_from_msc(time_msc, getattr(order, "time_done", None)),
            )
    else:
        print(f"Could not collect order history for {account_login}: {mt5.last_error()}")

    _save_collection_state(account_login, newest_deal_msc, newest_order_msc)


def get_recent_trade_events(limit=100):
    init_event_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT *
        FROM trade_events
        ORDER BY event_time DESC, id DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
