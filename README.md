# Binance USDT-M Futures Alert Bot for Telegram

**English** · [Русский](README.ru.md)

![tests](https://github.com/Bogdan131/binance-futures-alert-bot/actions/workflows/tests.yml/badge.svg)

A Telegram bot that watches Binance USDT-M futures and messages you when price, volume or a sharp move hits your condition. Each notification includes the condition, the current price, the 5-minute change, the volume multiple and a link to the chart. Only public Binance endpoints are used — no exchange API keys required.

## Commands

| Command | What it does |
| --- | --- |
| `/start` | Show help |
| `/add PEPE price > 0.0000125` | Alert when price goes above a level |
| `/add BTC price < 60000` | Alert when price goes below a level |
| `/add WIF volume x3` | Alert when 5-minute volume is more than 3× the average |
| `/add ORDI move 3%` | Alert on a move of more than 3% in 5 minutes, either direction |
| `/list` | List your alerts with their numbers; disabled ones are marked |
| `/del 4` | Delete your alert #4 |
| `/lang` | Show your current language and the available choices |
| `/lang en` or `/lang ru` | Switch replies and notifications to English or Russian |

Send commands in a private chat with the bot. `pepe` and `PEPEUSDT` both become `PEPEUSDT`. The symbol is checked against tradable Binance contracts quoted and margined in USDT. For prefixed contracts such as `1000PEPEUSDT`, use the exchange symbol and the contract price.

On a user's first command, the bot selects Russian for Telegram locales beginning with `ru` or `uk`, and English for other locales. You can change the saved language with `/lang en` or `/lang ru`. Notifications for alerts created before languages were added stay in Russian until that user sends any command.

## How alerts are evaluated

- **Price.** Compared with the latest ticker price. A price alert switches off after it fires; send the same `/add` again to re-enable it.
- **Volume.** The sum of the last five closed 1-minute candles is compared with the average 5-minute volume of the previous two hours (the 120 earlier candles divided by 24).
- **Move.** Percentage change between the close of the last candle and the close exactly five minutes earlier, compared in absolute value. Touching the threshold exactly does not trigger any alert.
- **Cooldown.** One alert fires at most once every 15 minutes by default. Re-adding the same condition keeps its number and cooldown. If Telegram returns an error, a price alert stays enabled and is retried after the cooldown.
- **Limits.** Up to 50 enabled alerts per user. If a user blocks the bot, their alerts are switched off.
- **Candles.** Requests are capped at 125 closed minutes via `endTime`. Volume and move need an unbroken history of the required length. For a price alert, candles are fetched only when the condition matches, to show the 5-minute change; if they are unavailable, the message says "no data" for that line.

A single `/fapi/v1/ticker/price` request fetches all prices per cycle (every 10 seconds by default), and a new cycle waits for the previous one to finish. Candles are cached for 30 seconds per symbol and requested only for symbols with active alerts. The contract list is loaded at start-up and refreshed hourly. Failed requests are retried on schedule (the symbol list after one minute), and Binance `Retry-After` is respected.

Alerts, last-fired times and language preferences are stored in `data/alerts.sqlite3`, created on first start.

## Telegram token

Open [@BotFather](https://t.me/BotFather), send `/newbot`, choose a name and a username ending in `bot`. Put the token you receive into `BOT_TOKEN` in `.env`. Keep that file local — it is excluded from Git. [Telegram docs on BotFather](https://core.telegram.org/bots/features#botfather)

## Run locally

Python 3.11 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

On Windows, activate with `.\.venv\Scripts\Activate.ps1` in PowerShell. Fill in `BOT_TOKEN` in `.env` and start the bot:

```bash
python -m bot.main
```

Open a private chat with your bot and send `/start`. `CHECK_SECONDS` and `COOLDOWN_MINUTES` (integers) in `.env` change the check interval and cooldown. Run one long-polling instance per token.

## Docker

Create `.env` from `.env.example` and set the token. The named volume keeps the SQLite database when the container is replaced.

```bash
docker build -t binance-futures-alert-bot .
docker run -d --name futures-alerts --restart unless-stopped \
  --env-file .env -v futures-alerts-data:/app/data binance-futures-alert-bot
docker logs -f futures-alerts
```

## VPS with systemd

Install Python 3.11+ with venv and copy the project to `/opt/binance-futures-alert-bot`. Set up `.venv` and `.env` there as in "Run locally". The service needs read access to the code and write access to `data`.

```bash
sudo useradd --system --user-group --no-create-home --shell /usr/sbin/nologin futures-alerts
sudo install -d -m 0750 -o futures-alerts -g futures-alerts /opt/binance-futures-alert-bot/data
sudo chown futures-alerts:futures-alerts /opt/binance-futures-alert-bot/.env
sudo chmod 600 /opt/binance-futures-alert-bot/.env
```

Save the unit file as `/etc/systemd/system/futures-alerts.service`:

```ini
[Unit]
Description=Telegram alerts for Binance USDT-M futures
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=futures-alerts
Group=futures-alerts
WorkingDirectory=/opt/binance-futures-alert-bot
ExecStart=/opt/binance-futures-alert-bot/.venv/bin/python -m bot.main
Environment=PYTHONUNBUFFERED=1
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now futures-alerts
sudo journalctl -u futures-alerts -f
```

## Tests

Tests use prepared candles, a temporary SQLite database and `httpx.MockTransport` — no token or network needed.

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

GitHub Actions runs the tests on Python 3.11–3.13 on every push.

`bot/checker.py` and `bot/commands.py` hold pure functions for calculations, conditions and command parsing, testable without Telegram. `bot/service.py` runs the background loop; Binance and SQLite access live in `market.py` and `storage.py`.

## Possible extensions

- Bybit and OKX futures with an exchange choice in the command.
- Open-interest growth or drop alerts.
- Wallet address tracking.
- In-bot subscription payments with per-plan alert limits.
