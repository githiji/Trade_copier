import yfinance as yf
import time
import MetaTrader5 as mt5

offset_history = []

def get_cfd_price(symbol):
    tick = mt5.symbol_info_tick(symbol)
    return tick.ask if tick else None


def get_nq_price(futures_ticker):
    data = yf.Ticker(futures_ticker)
    price = data.history(period="1m").tail(1)['Close'].values
    return price[0] if len(price) > 0 else None

def track_offset():
    nq = get_nq_price()
    cfd = get_cfd_price()
    if nq and cfd:
        offset = cfd - nq
        offset_history.append(offset)
        print(f"Futures: {nq:.2f}, CFD: {cfd:.2f}, Offset: {offset:.2f}")
        return offset
    return None

def entry_cfd(nq_entry_price):
     max_offset = max(offset_history) if offset_history else 0
     cfd_entry_price = nq_entry_price + max_offset
     return cfd_entry_price