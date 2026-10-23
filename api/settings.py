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

ALLOWED = ("start_date", "budget_spent_lakh", "savings_lakh", "autoresponder")

class handler(_Base):
    def do_GET(self):
        try:
            self._send(200, _store.get_settings())
        except Exception as e:
            self._send(500, {"error": str(e)})

    def do_POST(self):
        try:
            b = self._body()
            k, v = str(b["key"]), str(b.get("value", ""))[:40]
            if k not in ALLOWED:
                return self._send(400, {"error": "unknown setting"})
            _store.set_setting(k, v)
            self._send(200, {"ok": True})
        except (KeyError, ValueError, TypeError) as e:
            self._send(400, {"error": f"bad request: {e}"})
        except Exception as e:
            self._send(500, {"error": str(e)})
