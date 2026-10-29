# Satta Bazar React frontend

The React/Vite interface uses the Django API for market data, price history,
leaderboards, session authentication, wallet balances, and virtual trades.

## Run locally

1. Start Django from the repository root:

   ```powershell
   .\.venv\Scripts\python.exe manage.py runserver
   ```

2. In another terminal, start the frontend:

   ```powershell
   cd satta-bazar-frontend
   npm install
   npm run dev
   ```

3. Open the Vite URL shown in the terminal (normally
   [http://localhost:5173/](http://localhost:5173/)). Vite proxies `/api` requests
   to Django at `http://127.0.0.1:8000`. Set `VITE_DJANGO_ORIGIN` if Django is
   listening elsewhere.

The browser uses Django session cookies and obtains a CSRF token before
login, registration, logout, and trade requests. Market access is public;
trading requires a logged-in account.

Run `npm run build` to validate and build the frontend.
