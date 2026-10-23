import json, os, sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _store

class handler(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        try:
            self._send(200, _store.list_holds())
        except Exception as e:
            self._send(500, {"error": str(e)})

    def do_POST(self):
        """Log a request to hold purchase orders. This is a recommendation for procurement, not a change in Zoho."""
        try:
            b = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            rows = [dict(po=str(r["po"])[:60], sku=str(r["sku"])[:20], qty=int(r["qty"])) for r in b["pos"]][:50]
            if not rows:
                return self._send(400, {"error": "no purchase orders given"})
            _store.save_holds(rows, str(b.get("reason", ""))[:300])
            self._send(200, {"ok": True, "count": len(rows)})
        except (KeyError, ValueError, TypeError) as e:
            self._send(400, {"error": f"bad request: {e}"})
        except Exception as e:
            self._send(500, {"error": str(e)})
