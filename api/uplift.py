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

class handler(_Base):
    def do_GET(self):
        try:
            self._send(200, _store.list_uplifts())
        except Exception as e:
            self._send(500, {"error": str(e)})

    def do_POST(self):
        """Set a festival uplift for a category (scope "cat:Snack") or one SKU ("sku:SKU001"), in percent."""
        try:
            b = self._body()
            scope, pct = str(b["scope"])[:60], float(b["pct"])
            if not (scope.startswith("cat:") or scope.startswith("sku:")):
                return self._send(400, {"error": "scope must start with cat: or sku:"})
            if not (-50 <= pct <= 150):
                return self._send(400, {"error": "uplift must be between -50 and 150 percent"})
            by = str(b.get("by", "")).strip()[:60]
            if not by:
                return self._send(400, {"error": "a named person must make this change"})
            _store.save_uplift(scope, pct, str(b.get("note", ""))[:200], by)
            self._send(200, {"ok": True})
        except (KeyError, ValueError, TypeError) as e:
            self._send(400, {"error": f"bad request: {e}"})
        except Exception as e:
            self._send(500, {"error": str(e)})

    def do_DELETE(self):
        try:
            _store.delete_uplift((parse_qs(urlparse(self.path).query).get("scope") or [""])[0])
            self._send(200, {"ok": True})
        except Exception as e:
            self._send(500, {"error": str(e)})
