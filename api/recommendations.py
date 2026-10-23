import json, os, sys
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import run
import _zoho
import _store

def build(month=None, festival=None, demand_adj=0.0, simulate_shift=False, simulate_churn=False, live=False):
    """Run the engine; use live Zoho data when configured, falling back to the CSVs on any Zoho error."""
    data = os.path.join(ROOT, "data")
    zoho = dict(configured=_zoho.configured(), draft_enabled=_zoho.draft_enabled(), mode=_zoho.mode(), error=None)
    kw = {}
    if zoho["configured"]:
        try:
            item_map = _zoho.items()
            detail = _zoho.open_po_details(item_map)
            kw["open_po_detail"] = detail
            kw["open_po"] = {}
            for d in detail:
                kw["open_po"][d["sku"]] = kw["open_po"].get(d["sku"], 0) + d["qty"]
            if _zoho.sync_stock():
                kw["stock"] = _zoho.stock_on_hand(item_map)
                kw["today"] = (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime("%Y-%m-%d")
        except _zoho.ZohoError as e:
            zoho["error"] = str(e); kw = {}
    try:
        rules = _store.list_rules()
    except Exception:
        rules = {}
    common = dict(festival=festival, demand_adj=demand_adj, simulate_shift=simulate_shift, simulate_churn=simulate_churn, rules=rules, **kw)
    res = run(data, month, **common)
    if live:        # recompute with the latest mid-week regional shift applied to each affected SKU's demand
        shift = {}
        for reg in res["anomalies"]["regions"]:
            for sid in reg["skus"]:
                shift[sid] = reg["change_pct"] / 100
        res = run(data, month, sku_adj=shift, **common)
        res["live_adjustments"] = shift
    res["zoho"] = zoho
    return res

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        q = parse_qs(urlparse(self.path).query)
        month = (q.get("month") or [None])[0]
        fest = (q.get("festival") or [None])[0]
        fest = None if fest is None else fest.lower() in ("1", "true", "on")
        try:
            adj = max(-0.5, min(0.5, float((q.get("adj") or ["0"])[0]) / 100))   # what-if demand change, percent
            sc = (q.get("scenario") or [""])[0]
            live = (q.get("live") or [""])[0] in ("1", "true")
            body, code = json.dumps(build(month, fest, adj, sc == "shift", sc == "churn", live)).encode(), 200
        except Exception as e:
            body, code = json.dumps({"error": str(e)}).encode(), 500
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers(); self.wfile.write(body)
