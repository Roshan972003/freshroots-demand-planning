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
            self._send(200, _store.list_po_log())
        except Exception as e:
            self._send(500, {"error": str(e)})
