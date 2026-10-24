import json, os, sys
from http.server import BaseHTTPRequestHandler

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _zoho
import _store

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
            as_of = str(b.get("as_of", ""))
            approver = str(b.get("approver", "")).strip()[:60]
            # Human in the loop, enforced here and not only in the page: a named person must have approved this exact
            # quantity for this SKU before any purchase order is created.
            if not approver:
                return self._send(403, {"error": "an approver name is required to raise a PO"})
            d = _store.get_decision(as_of, sku)
            if not d or d["decision"] not in ("accepted", "overridden") or not d.get("decided_by"):
                return self._send(403, {"error": f"no human approval on record for {sku}: approve or override it first"})
            if int(d["final_qty"]) != qty:
                return self._send(403, {"error": f"quantity {qty} differs from the approved quantity {d['final_qty']}"})
            ref = f"DP {as_of} {sku} approved by {approver}".strip()
            po = _zoho.create_draft_po(sku, qty, os.path.join(HERE, "..", "data"), ref)
            _store.log_po(po.get("purchaseorder_number") or po.get("purchaseorder_id") or "", sku, qty, as_of, approver, po.get("status", "draft"))
            self._send(200, po)
        except (KeyError, ValueError, TypeError) as e:
            self._send(400, {"error": f"bad request: {e}"})
        except _zoho.ZohoInputError as e:
            self._send(400, {"error": str(e)})
        except _zoho.ZohoError as e:
            self._send(502, {"error": str(e)})
        except Exception as e:
            self._send(500, {"error": str(e)})
