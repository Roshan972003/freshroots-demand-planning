import json, os, sys
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import run
import _zoho

def build(month=None, festival=None, demand_adj=0.0):
    """Run the engine; use live Zoho data when configured, falling back to the CSVs on any Zoho error."""
    data = os.path.join(ROOT, "data")
    zoho = dict(configured=_zoho.configured(), draft_enabled=_zoho.draft_enabled(), mode=_zoho.mode(), error=None)
    kw = {}
    if zoho["configured"]:
        try:
            item_map = _zoho.items()
            kw["open_po"] = _zoho.open_po_units(item_map)
            if _zoho.sync_stock():
                kw["stock"] = _zoho.stock_on_hand(item_map)
                kw["today"] = (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime("%Y-%m-%d")
        except _zoho.ZohoError as e:
            zoho["error"] = str(e); kw = {}
    res = run(data, month, festival=festival, demand_adj=demand_adj, **kw)
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
            body, code = json.dumps(build(month, fest, adj)).encode(), 200
        except Exception as e:
            body, code = json.dumps({"error": str(e)}).encode(), 500
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers(); self.wfile.write(body)
