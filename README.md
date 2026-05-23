# 🚀 Multi-Account MT5 Trade Copier

<img width="1536" height="1024" alt="image" src="https://github.com/user-attachments/assets/3b6428ef-0ad2-4664-bf91-cfe97ceb39c1" />

A powerful Python-based **MetaTrader 5 Trade Copier** with a modern GUI built using **Tkinter**.  
This tool allows you to manage and execute trades across multiple prop firm or personal accounts simultaneously with advanced risk management features.

---

# ✨ Features

- ✅ Multi-account trade execution
- ✅ Market Buy / Sell buttons
- ✅ Pending Orders (Buy Stop / Sell Stop)
- ✅ Automatic lot size calculation
- ✅ Risk-based trading
- ✅ Manual lot override
- ✅ Auto close on target profit
- ✅ Auto close on max loss
- ✅ Live floating PnL tracking
- ✅ Close all trades instantly
- ✅ Break-even functionality
- ✅ Partial close support
- ✅ Supports brokers with custom symbols (`GBPUSD.qtr`, etc.)
- ✅ Modern compact trading interface
- ✅ MT5 integration using Python

---

# 🖥️ Preview

A lightweight desktop trading panel inspired by modern trading terminals.

---

# ⚙️ Technologies Used

- Python
- Tkinter
- MetaTrader5 Python API
- SQLite
- Threading

---

# 📦 Installation

## 1️⃣ Clone the Repository

```bash
git clone https://github.com/githiji/Trade_copier.git

cd trade-copier
```

---

## 2️⃣ Install Requirements

```bash
pip install MetaTrader5
```

Optional:

```bash
pip install pyinstaller
```

---

# ▶️ Running the Project

```bash
python copier.py
```

---

# 🛠️ Build Executable (.exe)

```bash
pyinstaller --onefile --windowed copier.py
```

Executable will appear inside:

```bash
dist/
```

---

# 📂 Project Structure

```bash
trade-copier/
│
├── copier.py
├── database.py
├── accounts.db
├── requirements.txt
└── README.md
```

---

# 📈 Features Explained

## 🔹 Risk Management

The copier automatically calculates lot size based on:

- Account balance
- Stop loss distance
- Risk percentage

Example:

```text
1% risk on every account automatically
```

---

## 🔹 Auto Close System

You can set:

- Target profit
- Maximum loss

The copier monitors floating PnL across all accounts and closes trades automatically.

---

## 🔹 Break Even

Move all positions to break even instantly with one click.

---

## 🔹 Partial Close

Close a percentage of open trades across all connected accounts.

Example:

```text
50% partial close
```

---

# 🧠 Supported Broker Symbols

The copier automatically detects symbols like:

```text
GBPUSD
GBPUSD.qtr
GBPUSDm
GBPUSD.pro
```

---

# 🔐 Disclaimer

This software is for educational purposes only.  
Trading involves risk. Use at your own responsibility.

---

# 🚀 Future Plans

- Linux support
- Broker API integration
- Web dashboard
- Mobile companion app
- Advanced analytics
- Trading journal integration
- AI trade assistant

---

# 👨‍💻 Author

Built by Brian Githinji trader & developer focused on automation, risk management, and prop firm trading systems.

---

# ⭐ Support

If you like this project:

- Star the repository ⭐
- Fork it 🍴
- Improve it 🔥

---

# 📜 License

MIT License
