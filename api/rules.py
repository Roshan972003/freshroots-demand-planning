import json, os, sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _store

class _Base(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers(); self.wfile.write(body)

    def _body(self):
        return json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")

RULE_TAGS = ("New launch", "Unusual distributor behavior", "One-off market event", "Competitor scheme", "Distributor onboarding",
             "Unseasonal weather", "Trade promotion", "Distributor anomaly", "Other")

class handler(_Base):
    def do_GET(self):
        try:
            self._send(200, _store.list_rules())
        except Exception as e:
            self._send(500, {"error": str(e)})

    def do_POST(self):
        """Create or replace a temporary (30-day) rule: scale this SKU's rule-based reorder quantity by `ratio`."""
        try:
            b = self._body()
            sku, ratio = str(b["sku"])[:20], float(b["ratio"])
            if not (0 <= ratio <= 5):
                return self._send(400, {"error": "ratio must be between 0 and 5"})
            tag = str(b.get("tag", ""))
            if tag not in RULE_TAGS:
                return self._send(400, {"error": "a reason tag is required"})
            _store.save_rule(sku, ratio, tag, str(b.get("reason", ""))[:300])
            self._send(200, {"ok": True})
        except (KeyError, ValueError, TypeError) as e:
            self._send(400, {"error": f"bad request: {e}"})
        except Exception as e:
            self._send(500, {"error": str(e)})

    def do_DELETE(self):
        try:
            _store.delete_rule((parse_qs(urlparse(self.path).query).get("sku") or [""])[0])
            self._send(200, {"ok": True})
        except Exception as e:
            self._send(500, {"error": str(e)})
