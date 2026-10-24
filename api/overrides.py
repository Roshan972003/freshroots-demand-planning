import json, os, sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _store

TAGS = ("New launch", "Unusual distributor behavior", "One-off market event", "Competitor scheme", "Distributor onboarding", "Unseasonal weather", "Trade promotion", "Distributor anomaly", "Live delta adjustment", "Other")

class handler(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        as_of = (parse_qs(urlparse(self.path).query).get("as_of") or [""])[0]
        try:
            self._send(200, _store.list_overrides(as_of))
        except Exception as e:
            self._send(500, {"error": str(e)})

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
            b = json.loads(self.rfile.read(n) or b"{}")
            as_of, sku, decision = str(b["as_of"]), str(b["sku"]), b["decision"]
            if decision not in ("accepted", "overridden"):
                return self._send(400, {"error": "decision must be accepted or overridden"})
            rec_qty = int(b.get("rec_qty") or 0)
            final_qty = int(b["final_qty"]) if decision == "overridden" else rec_qty
            if final_qty < 0:
                return self._send(400, {"error": "final_qty must be >= 0"})
            reason = (b.get("reason") or "")[:300]
            tag = (b.get("tag") or "")
            by = str(b.get("decided_by") or "").strip()[:60]
            if not by:
                return self._send(400, {"error": "decided_by is required: a named person must make every decision"})
            if tag and tag not in TAGS:
                return self._send(400, {"error": "unknown reason tag"})
            if decision == "overridden" and not (reason.strip() or tag):
                return self._send(400, {"error": "a reason tag or note is required when overriding"})
            _store.save_override(as_of, sku, decision, str(b.get("rec_status", "")), rec_qty, final_qty, reason, tag, by)
            self._send(200, {"ok": True})
        except (KeyError, ValueError, TypeError) as e:
            self._send(400, {"error": f"bad request: {e}"})
        except Exception as e:
            self._send(500, {"error": str(e)})

    def do_DELETE(self):
        q = parse_qs(urlparse(self.path).query)
        try:
            _store.delete_override((q.get("as_of") or [""])[0], (q.get("sku") or [""])[0])
            self._send(200, {"ok": True})
        except Exception as e:
            self._send(500, {"error": str(e)})
