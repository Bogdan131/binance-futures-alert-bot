# Telegram-бот алертов Binance USDT-M

![tests](https://github.com/Bogdan131/binance-futures-alert-bot/actions/workflows/tests.yml/badge.svg)

Бот отслеживает цену, объём и движение фьючерсов Binance. При срабатывании он присылает в личный чат условие алерта, текущую цену, изменение за пять минут, кратность объёма и ссылку на график. Для рыночных данных используются публичные эндпоинты Binance.

## Команды

| Команда | Действие |
| --- | --- |
| `/start` | Показать подсказку |
| `/add PEPE price > 0.0000125` | Добавить алерт на цену выше порога |
| `/add BTC price < 60000` | Добавить алерт на цену ниже порога |
| `/add WIF volume x3` | Следить за ростом пятиминутного объёма более чем в три раза |
| `/add ORDI move 3%` | Следить за движением цены больше 3% в любую сторону за пять минут |
| `/list` | Показать алерты с номерами и отметить выключенные |
| `/del 4` | Удалить свой алерт № 4 |

Отправляй команды в личном чате с ботом. Введённые `pepe` и `PEPEUSDT` приводятся к `PEPEUSDT`. Бот сверяет символ с торгуемыми контрактами Binance, для которых валюта котировки и маржи — USDT. Для контракта с префиксом, например `1000PEPEUSDT`, укажи его биржевой символ и цену контракта.

## Как считаются алерты

- **Цена.** Сравнивается последняя цена из тикера. После уведомления ценовой алерт выключается. Повтори ту же команду `/add`, чтобы включить его снова.
- **Объём.** Сумма объёмов последних пяти закрытых минутных свечей сравнивается со средним пятиминутным объёмом предыдущих двух часов. Среднее равно сумме объёмов предшествующих 120 свечей, делённой на 24.
- **Движение.** Изменение в процентах считается по ценам закрытия последней свечи и свечи ровно на пять минут раньше. Сравнивается абсолютное значение изменения. Во всех условиях равенство порогу срабатывания не вызывает.
- **Интервал уведомлений.** Один алерт срабатывает не чаще раза в 15 минут по умолчанию. Повторное добавление того же условия сохраняет номер и отсчёт интервала. Если Telegram вернул ошибку, ценовой алерт остаётся включённым, а следующая попытка возможна после интервала.
- **Лимит.** У одного пользователя может быть до 50 включённых алертов. Если пользователь заблокировал бота, его алерты выключаются.
- **Свечи.** Запрос ограничен 125 закрытыми минутами через `endTime`. Объём и движение проверяются при наличии непрерывной истории нужной длины. Для ценового алерта свечи запрашиваются при совпадении условия, чтобы показать изменение в уведомлении. При недоступности свечей сообщение о цене приходит с пометкой «нет данных» за пять минут.

Один запрос `/fapi/v1/ticker/price` получает цены всех контрактов за цикл, по умолчанию каждые 10 секунд. Повторный цикл ждёт завершения предыдущего. Свечи кешируются на 30 секунд на символ, а запросы делаются по символам проверяемых алертов. Список контрактов загружается при запуске и обновляется раз в час. При ошибках запросы повторяются по расписанию, для списка символов — через минуту. При ограничениях Binance учитывается `Retry-After`.

Алерты и время последнего срабатывания хранятся в `data/alerts.sqlite3`. Каталог и таблица создаются при запуске.

## Токен Telegram

Открой [@BotFather](https://t.me/BotFather), отправь `/newbot` и задай имя и username, который заканчивается на `bot`. Скопируй выданный токен в значение `BOT_TOKEN` в файле `.env`. Держи этот файл локально, он исключён из Git. [Справка Telegram о BotFather](https://core.telegram.org/bots/features#botfather)

## Локальный запуск

Нужен Python 3.11 или новее. Из каталога проекта выполни команды ниже.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

В Windows активируй окружение через `\.venv\Scripts\Activate.ps1` в PowerShell. Заполни `BOT_TOKEN` в `.env` и запусти бота.

```bash
python -m bot.main
```

Открой личный чат с ботом в Telegram и отправь `/start`. При необходимости измени целочисленные `CHECK_SECONDS` и `COOLDOWN_MINUTES` в `.env`. Запускай один экземпляр long polling на токен.

## Docker

Создай `.env` из `.env.example` и заполни токен. Именованный том сохраняет SQLite при замене контейнера.

```bash
docker build -t binance-futures-alert-bot .
docker run -d --name futures-alerts --restart unless-stopped \
  --env-file .env -v futures-alerts-data:/app/data binance-futures-alert-bot
docker logs -f futures-alerts
```

## VPS с systemd

Установи Python 3.11+ с модулем venv и скопируй проект в `/opt/binance-futures-alert-bot`. Настрой там `.venv` и `.env` по шагам локального запуска. Сервису нужен доступ на чтение исходников и право записи в `data`.

```bash
sudo useradd --system --user-group --no-create-home --shell /usr/sbin/nologin futures-alerts
sudo install -d -m 0750 -o futures-alerts -g futures-alerts /opt/binance-futures-alert-bot/data
sudo chown futures-alerts:futures-alerts /opt/binance-futures-alert-bot/.env
sudo chmod 600 /opt/binance-futures-alert-bot/.env
```

Сохрани unit-файл в `/etc/systemd/system/futures-alerts.service`.

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

## Тесты

Тесты используют подготовленные свечи, временную SQLite и `httpx.MockTransport`. Для них не нужен токен и доступ к сети.

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

GitHub Actions запускает тесты на Python 3.11–3.13 при каждом push.

В `bot/checker.py` и `bot/commands.py` находятся чистые функции расчёта, проверки условий и разбора команд, их можно тестировать без Telegram. В `bot/service.py` выполняется фоновый цикл, а доступ к Binance и SQLite вынесен в `market.py` и `storage.py`.

## Что можно доработать под заказчика

- Добавить фьючерсы Bybit и OKX с выбором биржи в команде.
- Уведомлять о росте или снижении открытого интереса.
- Отслеживать события по адресам кошельков.
- Подключить оплату подписки в боте и лимиты алертов по тарифу.
