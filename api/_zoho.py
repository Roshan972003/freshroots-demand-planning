"""Zoho Inventory client (stdlib only). Reads open purchase orders and stock; can create DRAFT purchase orders.

Config (Vercel env vars, never in code):
  ZOHO_CLIENT_ID, ZOHO_CLIENT_SECRET, ZOHO_REFRESH_TOKEN, ZOHO_ORG_ID   required
  ZOHO_MODE=mock             simulated Zoho (demo sandbox) instead; no credentials needed
  ZOHO_DC                    data center suffix: in (default), com, eu, com.au
  ZOHO_SYNC_STOCK=true       use Zoho stock on hand instead of data/current_inventory.csv
  ZOHO_OPEN_PO_STATUSES      comma list of PO statuses counted as open (default: open)
  ZOHO_ALLOW_DRAFT_PO=true   enable creating draft POs
  ZOHO_DEFAULT_VENDOR_ID     vendor for draft POs (per-SKU override: data/zoho_vendors.csv with SKU_ID,Vendor_ID)
Scopes needed: ZohoInventory.items.READ, ZohoInventory.purchaseorders.READ (+ .CREATE for drafts).
"""
import csv, json, os, time, urllib.error, urllib.parse, urllib.request

class ZohoError(Exception):
    pass

class ZohoInputError(ZohoError):
    """The caller asked for something invalid (bad SKU or quantity), as opposed to Zoho failing."""

def _env(k, d=""):
    return os.environ.get(k, d)

def mock_mode():
    """ZOHO_MODE=mock uses the in-app simulated Zoho (api/_mock_zoho.py), for demos without a real Zoho account."""
    return _env("ZOHO_MODE").lower() == "mock"

def mode():
    return "demo" if mock_mode() else "live"

def configured():
    if mock_mode():
        return True
    return all(_env(k) for k in ("ZOHO_CLIENT_ID", "ZOHO_CLIENT_SECRET", "ZOHO_REFRESH_TOKEN", "ZOHO_ORG_ID"))

def sync_stock():
    return _env("ZOHO_SYNC_STOCK").lower() in ("1", "true", "yes")

def draft_enabled():
    return configured() and _env("ZOHO_ALLOW_DRAFT_PO").lower() in ("1", "true", "yes")

def _http(method, url, headers=None, body=None):
    if mock_mode():
        import _mock_zoho
        return _mock_zoho.respond(method, url, body)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=dict(headers or {}))
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        raise ZohoError(f"Zoho HTTP {e.code}: {e.read()[:200].decode(errors='replace')}")
    except urllib.error.URLError as e:
        raise ZohoError(f"Zoho unreachable: {e.reason}")

_tok = {"v": None, "exp": 0.0}

def _token():
    if _tok["v"] and time.time() < _tok["exp"] - 60:
        return _tok["v"]
    q = urllib.parse.urlencode({"refresh_token": _env("ZOHO_REFRESH_TOKEN"), "client_id": _env("ZOHO_CLIENT_ID"),
                                "client_secret": _env("ZOHO_CLIENT_SECRET"), "grant_type": "refresh_token"})
    r = _http("POST", f"https://accounts.zoho.{_env('ZOHO_DC', 'in')}/oauth/v2/token?{q}")
    if "access_token" not in r:
        raise ZohoError(f"Zoho auth failed: {r.get('error', r)}")
    _tok["v"], _tok["exp"] = r["access_token"], time.time() + int(r.get("expires_in", 3600))
    return _tok["v"]

def _api(method, path, params=None, body=None):
    p = dict(params or {}, organization_id=_env("ZOHO_ORG_ID"))
    url = f"https://www.zohoapis.{_env('ZOHO_DC', 'in')}/inventory/v1/{path}?{urllib.parse.urlencode(p)}"
    r = _http(method, url, {"Authorization": f"Zoho-oauthtoken {_token()}"}, body)
    if r.get("code", 0) != 0:
        raise ZohoError(f"Zoho API error {r.get('code')}: {r.get('message')}")
    return r

def _pages(path, key, params=None):
    page, out = 1, []
    while True:
        r = _api("GET", path, dict(params or {}, page=page, per_page=200))
        out += r.get(key, [])
        if not (r.get("page_context") or {}).get("has_more_page") or page >= 20:
            return out
        page += 1

def items():
    """sku code -> item dict (item_id, stock_on_hand, ...)."""
    return {i["sku"]: i for i in _pages("items", "items") if i.get("sku")}

def stock_on_hand(item_map=None):
    """sku -> units on hand. Only items whose list entry carries a stock figure are returned; if none do, raise so
    the app falls back to the CSV instead of reading missing data as zero stock (which would flag every SKU)."""
    m = item_map or items()
    out = {sku: int(float(i["stock_on_hand"])) for sku, i in m.items() if i.get("stock_on_hand") not in (None, "")}
    if m and not out:
        raise ZohoError("Zoho's item list did not include stock_on_hand; keeping stock from the CSV")
    return out

def open_po_units(item_map=None):
    """sku code -> units ordered but not yet received, across open purchase orders."""
    out = {}
    for d in open_po_details(item_map):
        out[d["sku"]] = out.get(d["sku"], 0) + d["qty"]
    return out

SKIP_PO_STATUS = {"draft", "cancelled", "canceled", "closed", "void", "rejected", "pending_approval", "declined"}

def open_po_details(item_map=None):
    """[{po, sku, qty}] for each purchase order line with units still to receive.
    Lists all POs (the status filter values are not documented), skips draft/cancelled/closed ones, then reads each
    remaining PO's lines: quantity minus quantity_received. At most ZOHO_MAX_PO_DETAILS POs are read (default 60)
    to stay inside Zoho's 100 requests/minute limit."""
    item_map = item_map or items()
    by_id = {i["item_id"]: sku for sku, i in item_map.items()}
    cap = int(_env("ZOHO_MAX_PO_DETAILS", "60") or 60)
    out, read = [], 0
    for po in _pages("purchaseorders", "purchaseorders"):
        if str(po.get("status", "")).lower() in SKIP_PO_STATUS:
            continue
        if read >= cap:
            break
        read += 1
        d = _api("GET", f"purchaseorders/{po['purchaseorder_id']}")
        detail = d.get("purchaseorder") or d.get("purchase_order") or {}
        number = po.get("purchaseorder_number") or detail.get("purchaseorder_number") or po["purchaseorder_id"]
        for ln in detail.get("line_items", []):
            sku = by_id.get(ln.get("item_id")) or ln.get("sku")
            left = float(ln.get("quantity") or 0) - float(ln.get("quantity_received") or 0)
            if sku and left > 0:
                out.append(dict(po=number, sku=sku, qty=int(left)))
    return out

def _vendor_for(sku, data_dir):
    path = os.path.join(data_dir, "zoho_vendors.csv")
    if os.path.exists(path):
        with open(path, newline="") as f:
            for r in csv.DictReader(f):
                if r["SKU_ID"] == sku and r.get("Vendor_ID"):
                    return r["Vendor_ID"]
    v = _env("ZOHO_DEFAULT_VENDOR_ID") or ("Demo Supplier" if mock_mode() else "")
    if not v:
        raise ZohoError("No vendor for this SKU: set ZOHO_DEFAULT_VENDOR_ID or add it to data/zoho_vendors.csv")
    return v

def create_draft_po(sku, qty, data_dir, reference=""):
    if not draft_enabled():
        raise ZohoError("Draft PO creation is not enabled")
    if qty <= 0:
        raise ZohoInputError("Quantity must be positive")
    item = items().get(sku)
    if not item:
        raise ZohoInputError(f"SKU {sku} not found in Zoho items")
    body = {"vendor_id": _vendor_for(sku, data_dir), "reference_number": reference[:50],
            "notes": "Draft created by Freshroots demand planning tool. Review before issuing.",
            "line_items": [{"item_id": item["item_id"], "quantity": qty}]}
    try:
        resp = _api("POST", "purchaseorders", body=body)
    except ZohoError as e:
        # Zoho documents purchaseorder_number as required; with auto-numbering on it is normally optional.
        # If it is rejected for that reason, retry once with a number we generate.
        if "number" not in str(e).lower():
            raise
        import time
        resp = _api("POST", "purchaseorders", body=dict(body, purchaseorder_number=f"DP-{int(time.time())}"))
    po = resp.get("purchaseorder") or resp.get("purchase_order") or {}
    return {"purchaseorder_id": po.get("purchaseorder_id"), "purchaseorder_number": po.get("purchaseorder_number"),
            "status": po.get("status", "draft")}
