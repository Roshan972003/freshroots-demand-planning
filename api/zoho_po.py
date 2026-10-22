import json, os, sys
from http.server import BaseHTTPRequestHandler

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _zoho

class handler(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers(); self.wfile.write(body)

    def do_POST(self):
        """Create a DRAFT purchase order in Zoho for one SKU. A person still reviews and issues it in Zoho."""
        try:
            n = int(self.headers.get("Content-Length") or 0)
            b = json.loads(self.rfile.read(n) or b"{}")
            sku, qty = str(b["sku"]), int(b["qty"])
            ref = f"DP {b.get('as_of', '')} {sku}".strip()
            self._send(200, _zoho.create_draft_po(sku, qty, os.path.join(HERE, "..", "data"), ref))
        except (KeyError, ValueError, TypeError) as e:
            self._send(400, {"error": f"bad request: {e}"})
        except _zoho.ZohoError as e:
            self._send(502, {"error": str(e)})
        except Exception as e:
            self._send(500, {"error": str(e)})
