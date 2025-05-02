# Binance Launchpool Auto-Trader 🚀

This is my first ever Python script, built from scratch with tons of guidance from ChatGPT ❤️

It’s a fully automated trading bot for Binance Launchpool events. When Binance opens trading for a newly launched coin, this bot:

- 📉 Instantly sells at market price if the price falls
- 📈 Places a trailing stop sell order if the price starts rising

---

## ⚙️ Features

- Real-time price tracking with WebSocket
- Automatically chooses between Market and Trailing Stop orders
- Trailing Stop % adapts based on coin price
- Whole number quantity truncation for safe sells
- Detailed logging (testnet/mainnet split)
- Discord webhook notifications
- Configurable thresholds
- Testnet mode for safe testing

---

## 🛠 Requirements

```bash
pip install -r requirements.txt
```

---

## 🔧 Configuration

Rename `config-example.json` to `config.json` and edit the values:

```json
{
  "api_key": "your_mainnet_api_key",
  "api_secret": "your_mainnet_api_secret",
  "testnet_api_key": "your_testnet_api_key",
  "testnet_api_secret": "your_testnet_api_secret",
  "symbol": "HYPERUSDC",
  "price_rise_threshold_seconds": 2,
  "trailing_auto_cancel_seconds": 30,
  "testnet": false,
  "discord_webhook": "https://discord.com/api/webhooks/..."
}
```

---

## 🚀 Usage

1. Set `symbol` to the coin being listed (e.g., `"WCTUSDC"`).
2. Set `testnet: true` to test or `false` to trade real funds.
3. Start the bot 1–5 minutes before launch:
```bash
python trade.py
```

Watch console logs or Discord for results.

---

## 🧪 Notes on Testnet

Testnet mode can simulate trades using testnet API keys.
It will also auto-buy 1 coin if none are present to sell.

---

## ⚠️ Disclaimers

- Trading carries risk. This is **experimental software**.
- You are responsible for your API keys and any losses.
- Never upload `config.json` publicly.

---

## 🧠 Contributors

- **You** – For coding your first Python script!
- **ChatGPT** – For explaining everything line-by-line and helping it work under pressure 😄

---

## 📄 License

MIT License. Use responsibly.
