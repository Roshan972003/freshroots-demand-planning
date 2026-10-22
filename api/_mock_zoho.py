"""Simulated Zoho Inventory API for demos when no real Zoho account is available (ZOHO_MODE=mock).

Answers the same request shapes api/_zoho.py sends to the real API, from the CSVs in data/ plus
data/mock_zoho_pos.json. Draft POs created through it are kept in the app database. It is a simulation:
nothing here talks to Zoho, and the app labels results as "demo sandbox".
"""
import csv, json, os, urllib.parse
import _store

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")

def _rows(name):
    with open(os.path.join(DATA, name), newline="") as f:
        return list(csv.DictReader(f))

def _items():
    stock = {r["SKU_ID"]: r["Units_On_Hand"] for r in _rows("current_inventory.csv")}
    return [{"item_id": f"DEMO-{r['SKU_ID']}", "name": r["SKU_Name"], "sku": r["SKU_ID"],
             "stock_on_hand": stock.get(r["SKU_ID"], "0")} for r in _rows("sku_master.csv")]

def _pos():
    with open(os.path.join(DATA, "mock_zoho_pos.json")) as f:
        pos = json.load(f)["purchaseorders"]
    return pos + _store.list_mock_pos()

def _lines(po):
    by_sku = {i["sku"]: i["item_id"] for i in _items()}
    return [dict(l, item_id=by_sku.get(l["sku"], l.get("item_id"))) for l in po["line_items"]]

def respond(method, url, body=None):
    u = urllib.parse.urlparse(url)
    q = dict(urllib.parse.parse_qsl(u.query))
    path = u.path
    if "oauth/v2/token" in path:
        return {"access_token": "demo-token", "expires_in": 3600}
    page, per = int(q.get("page", 1)), int(q.get("per_page", 200))
    def paged(key, rows):
        chunk = rows[(page - 1) * per: page * per]
        return {"code": 0, "message": "success", key: chunk, "page_context": {"page": page, "has_more_page": page * per < len(rows)}}
    if path.endswith("/items"):
        return paged("items", _items())
    if path.endswith("/purchaseorders") and method == "GET":
        want = q.get("status")
        rows = [{"purchaseorder_id": p["purchaseorder_id"], "purchaseorder_number": p["purchaseorder_number"], "status": p["status"]}
                for p in _pos() if not want or p["status"] == want]
        return paged("purchaseorders", rows)
    if "/purchaseorders/" in path and method == "GET":
        pid = path.rsplit("/", 1)[1]
        po = next((p for p in _pos() if p["purchaseorder_id"] == pid), None)
        if not po:
            return {"code": 1002, "message": "purchase order does not exist"}
        return {"code": 0, "purchaseorder": dict(po, line_items=_lines(po))}
    if path.endswith("/purchaseorders") and method == "POST":
        by_id = {i["item_id"]: i["sku"] for i in _items()}
        lines = [{"sku": by_id.get(l["item_id"]), "item_id": l["item_id"], "quantity": l["quantity"], "quantity_received": 0}
                 for l in body["line_items"]]
        po = _store.save_mock_po(body.get("vendor_id", ""), body.get("reference_number", ""), lines)
        return {"code": 0, "message": "The purchase order has been created.", "purchaseorder": po}
    return {"code": 5, "message": f"invalid URL {path}"}
