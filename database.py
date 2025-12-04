
import sqlite3
import sys
import os

# Ensure current dir is in path for local imports to work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


def init_db():
    conn = sqlite3.connect("accounts.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            login TEXT NOT NULL,
            server TEXT NOT NULL,
            password TEXT NOT NULL,
            path TEXT NOT NULL,
            enabled INTEGER DEFAULT 1
        )
    ''')
    conn.commit()
    conn.close()

def get_accounts():
    conn = sqlite3.connect("accounts.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM accounts")
    accounts = cursor.fetchall()
    conn.close()
    return accounts
def add_account(login, server, password, path):
    conn = sqlite3.connect("accounts.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO accounts (login, server, password,path) VALUES (?, ?, ?,?)", (login, server, password,path))
    conn.commit()
    conn.close()

def remove_account(account_id):
    conn = sqlite3.connect("accounts.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
    conn.commit()
    conn.close()

def toggle_account(account_id, enable):
    conn = sqlite3.connect("accounts.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE accounts SET enabled = ? WHERE id = ?", (enable, account_id))
    conn.commit()
    conn.close()

# Call this once at the start
init_db()
def get_accounts_for_copier():
    conn = sqlite3.connect("accounts.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM accounts")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
