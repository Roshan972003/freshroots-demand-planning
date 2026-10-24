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

## Zoho demo sandbox (no Zoho account needed)
`ZOHO_MODE=mock` makes the app talk to a **simulated** Zoho Inventory (`api/_mock_zoho.py`) through the same client code as the real link: open POs and stock come from `data/` and `data/mock_zoho_pos.json`, and draft POs created with the button are stored in the app database. The header says "Zoho DEMO SANDBOX, simulated". It is a stand-in for demos and testing, not real Zoho data. Remove `ZOHO_MODE` and add real credentials (below) to go live.

## Zoho Inventory link (optional, off until env vars are set)
Read-only by default: live open purchase orders count as stock. Falls back to the CSVs if Zoho is unreachable, and the dashboard says so.
1. In the Zoho API console (api-console.zoho.in, or your data center) create a **Self Client**. Scopes: `ZohoInventory.items.READ,ZohoInventory.purchaseorders.READ` (add `ZohoInventory.purchaseorders.CREATE` only for draft POs). Generate a grant code and exchange it once for a **refresh token**.
2. In Vercel > Settings > Environment Variables add: `ZOHO_CLIENT_ID`, `ZOHO_CLIENT_SECRET`, `ZOHO_REFRESH_TOKEN`, `ZOHO_ORG_ID` (Zoho Inventory > Settings > Organization Profile), and `ZOHO_DC` (`in` default, `com`, `eu`, `com.au`). Mark the secrets Sensitive.
3. Optional: `ZOHO_SYNC_STOCK=true` (use Zoho stock instead of `current_inventory.csv`), `ZOHO_OPEN_PO_STATUSES` (default `open`), `ZOHO_ALLOW_DRAFT_PO=true` plus `ZOHO_DEFAULT_VENDOR_ID` (or `data/zoho_vendors.csv` with SKU_ID,Vendor_ID) to show a "Create draft PO in Zoho" button after a decision. Drafts only: a person reviews and issues them in Zoho.
4. Zoho item SKU codes must match the SKU IDs here (SKU001...). Redeploy.
A full Zoho read takes about 4 seconds, so the app reuses it for `ZOHO_CACHE_SECONDS` (default 45). Add `?fresh=1` to `/api/recommendations` to force a new read. If Zoho fails, the last good read is shown with a warning.

Human-in-the-loop and festival-uplift tests (through the real handlers): `python3 -m unittest tests.test_hitl -v`.

Tests with a mocked Zoho: `python3 -m unittest tests.test_zoho -v`. **Verified once against a real Zoho Inventory account (India data center) on 24 Oct 2026: items and stock read correctly, open POs read as ordered minus received, and a draft PO was created without a supplied PO number.**

Checked against Zoho's published API docs; the three points marked (confirmed) were also confirmed on that real run:
- Auth header `Zoho-oauthtoken`, base `https://www.zohoapis.<dc>/inventory/v1`, `organization_id` on every call, 100 requests/minute per organization (the client reads at most `ZOHO_MAX_PO_DETAILS` purchase orders, default 60).
- The items list may not include `stock_on_hand` (confirmed: it does for this account). If it doesn't, stock sync raises and the app keeps the CSV stock and shows a warning, rather than treating missing stock as zero.
- Purchase orders are listed without a status filter (its values are undocumented); draft, cancelled and closed ones are skipped, and open units are `quantity - quantity_received` per line.
- Zoho documents `purchaseorder_number` as required when creating a PO (confirmed: auto-numbering accepted the request without one). The client first omits it (works with auto-numbering) and retries once with a generated `DP-<timestamp>` if Zoho rejects that.
- Response wrapper keys `purchaseorder` and `purchase_order` are both accepted.

## Open purchase orders from CSV (used when Zoho is not configured)
`data/open_orders.csv` (PO_Number, SKU_ID, Quantity, Expected_Date), exported from Zoho. Units on order count as stock in the cover checks. Leave it header-only if there is nothing open. No Zoho API is used.

Layout: `public/index.html` (UI), `api/recommendations.py` (runs `engine.py` on `data/`), `api/overrides.py` (accept/override records in Postgres).

## More
- `docs/components-map.svg`: components map (who does what, in order). Regenerate with `python3 docs/make_components_map.py`
- `DECISION.md`: Nine Checks and Five Pre-Build Decisions
- `BACKTEST.md`: first replay of the rules and its limits
- `WALKTHROUGH.md`: demo script
- `build_dashboard.py` / `out/dashboard.html`: an older static view, kept for offline use
- `DATA_REQUEST.md`: message asking IT for the data the real backtest needs
