# Satta Bazar

Satta Bazar is a Hinglish, meme-driven virtual stock-market game. It uses fictional
assets and virtual Bazar Bucks (BB) only; it has no deposits, withdrawals,
betting, prizes, or payment processing.

## What is implemented

- Django 5.2 project, custom UUID user, Django-hashed passwords and **session
  authentication**. The project does not use or issue JWTs.
- Local SQLite storage, REST API under `/api/v1/`, pagination, throttling,
  OpenAPI schema and API guide.
- A playable server-rendered browser page at `/`: register/login, browse assets,
  buy/sell virtual positions, check portfolio, claim a daily reward, and follow
  market events.
- 25 configurable fictional assets and 25 bounded event templates, added by a
  repeatable seed command.
- Server-priced spot trades, integer-safe decimal accounting, wallet ledger,
  idempotency keys, long-only positions, partial/full sells, P&L, and audited
  staff adjustments.
- Bounded stochastic price updates, reproducible simulation seeds, price
  snapshots, pause controls, event validation, price-retention command.
- YOLO, Papa Ki Pari and Market Ka Postmortem round modes, isolated round price
  state, transitions, scheduled round events, and round summaries.
- Daily rewards, missions, achievements/XP/levels, leaderboards, Hinglish/English
  trade roasts, read-only accounting admin screens.
- Session-authenticated private WebSockets and explicitly subscribed public
  price/event/round feeds. Reconnect recovery is via REST.

## Local Windows setup

The project has no Docker/PostgreSQL/Redis setup. Its local Channels layer uses
in-memory groups (single-process development only); run one Django ASGI server
process. A local management-command scheduler replaces Celery until external
infrastructure is added.

1. Use Python 3.12 or newer.
2. Create and activate a virtual environment:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. Install dependencies. On Windows/Python 3.15, Autobahn's optional C extension
   requires a compiler; set the environment variable below to use its
   pure-Python implementation:

   ```powershell
   $env:AUTOBAHN_USE_NVX = "0"
   python -m pip install -r requirements-dev.txt
   ```

4. Copy `.env.example` to `.env` if you want to configure the virtual starting
   balance or Django secret. Local development supplies a development-only
   secret if none is set.
5. Apply migrations, seed catalog data, and create an admin user:

   ```powershell
   python manage.py migrate
   python manage.py seed_game
   python manage.py createsuperuser
   ```

6. In one terminal run the local market/round scheduler:

   ```powershell
   python manage.py run_market
   ```

   Use `python manage.py run_market --once --seed 10` for one reproducible tick.
   The scheduler uses the configured market interval; price updates can be
   exercised directly with `python manage.py simulate_market --ticks 5 --seed 10`.
7. In another terminal run the app:

   ```powershell
   python manage.py runserver
   ```

Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/). Admin is at
`/admin/`, health at `/health/`, API guide at `/api/docs/`, and the OpenAPI
schema at `/api/schema/`.

## Authentication and API notes

Browser/API login uses Django sessions. Before browser `POST` requests, obtain a
CSRF cookie from `GET /api/v1/auth/csrf/` and send its value in `X-CSRFToken`.
The website does this automatically. Public price/catalog/news reads do not
require login; wallet, trading, portfolio, claims and private WebSockets do.
`POST /api/v1/auth/password-reset/` always returns a non-enumerating response.
Development reset mail is written to the runserver console; configure a real
email backend before production.

Representative requests:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/assets/
python manage.py adjust_wallet --actor admin --wallet <wallet-uuid> --amount 100 --reason "Documented test adjustment"
```

Trades accept `symbol`, `quantity`, and a unique `idempotency_key`; price,
balances and P&L are always computed by the server.

## Operations and verification

```powershell
python manage.py check
python manage.py test apps.accounts apps.game
python manage.py makemigrations --check --dry-run
ruff check apps config manage.py
python manage.py prune_price_history --days 30
```

The retention command removes price snapshots older than 30 days by default.
Run it periodically if history should be bounded. Portfolio snapshots are
captured once daily by the scheduler and after trades.

## Scope and limitations

SQLite is suitable for local development, not the row-locking and concurrency
guarantees required for production trading. The SQLite tests verify atomic
service behavior and duplicate-request handling, **not PostgreSQL-backed
concurrency guarantees**. The in-memory WebSocket channel layer also does not
share messages between server processes. Production deployment needs the
PostgreSQL/Redis infrastructure, durable channel layer, background workers,
monitoring, backups, real email, and deployment-specific security settings.
Production settings intentionally fail closed until a non-SQLite database,
secret, allowed hosts, and email backend are configured.
