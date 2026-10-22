# Freshroots Demand Planning

**Live app:** https://freshroots-demand-planning-indol.vercel.app  (no login; accept/override records are saved to Neon Postgres)

Rules engine (Raghav's documented rules) + dashboard with accept/override capture. Why this was chosen: `DECISION.md`. Backtest: `BACKTEST.md`.

## Run locally
```
python3 dev.py          # http://localhost:3000, overrides saved to a local SQLite file
python3 engine.py       # CSV/JSON recommendations in out/
./run_weekly.sh         # refresh outputs + archive (cron-friendly)
```

## Deploy to Vercel
1. Push this folder to a GitHub repo and import it at vercel.com/new (framework preset: Other).
2. In the project: Storage > Create > Neon Postgres (connects and sets `DATABASE_URL` automatically).
3. Redeploy. Refresh data by replacing the CSVs in `data/` and pushing.

## Open purchase orders (optional)
`data/open_orders.csv` (PO_Number, SKU_ID, Quantity, Expected_Date), exported from Zoho. Units on order count as stock in the cover checks. Leave it header-only if there is nothing open. No Zoho API is used.

Layout: `public/index.html` (UI), `api/recommendations.py` (runs `engine.py` on `data/`), `api/overrides.py` (accept/override records in Postgres).

## More
- `DECISION.md`: Nine Checks and Five Pre-Build Decisions
- `BACKTEST.md`: first replay of the rules and its limits
- `WALKTHROUGH.md`: 2-minute demo script
- `DATA_REQUEST.md`: message asking IT for the data the real backtest needs
