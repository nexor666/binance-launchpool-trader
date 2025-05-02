# Installation Guide for Binance Launchpool Trader

This guide walks you through setting up the environment to run the trade bot on a fresh Debian server.

---

## Prerequisites
- Python 3.11+
- `git` installed
- Internet access

---

## 1. Clone the Repository
```bash
git clone https://github.com/nexor666/binance-launchpool-trader.git
cd binance-launchpool-trader
```

## 2. Create Python Virtual Environment
```bash
python3 -m venv binance-env
source binance-env/bin/activate
```

## 3. Install Dependencies
```bash
pip install -r requirements.txt
```

## 4. Configure Your Bot
Rename and edit the example config file:
```bash
cp config-example.json config.json
nano config.json
```
Add your API keys, symbol, and other settings.

---

## 5. Run the Bot
```bash
python trade.py
```

---

## Optional: Update Later
If you want to pull updates from your GitHub:
```bash
git pull origin main
```

---

## Notes
- Only `config.json` contains sensitive info. Never upload it.
- Make sure your system clock is accurate for timely trades.
- Test thoroughly in testnet mode before going live.

---

Created by: **Nexor**  
Major Contributor: **ChatGPT by OpenAI**
