# Freshroots Demand Planning

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

Layout: `public/index.html` (UI), `api/recommendations.py` (runs `engine.py` on `data/`), `api/overrides.py` (accept/override records in Postgres).
