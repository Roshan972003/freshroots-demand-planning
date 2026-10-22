"""Mocked Zoho tests (no network). Run: python3 -m unittest tests.test_zoho -v"""
import os, sys, unittest, urllib.parse
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "api"))
import _zoho
from api import recommendations

ITEMS = [{"item_id": f"I{n}", "sku": f"SKU{n:03d}", "stock_on_hand": 100 * n} for n in range(1, 16)]
CALLS = []

def fake_http(method, url, headers=None, body=None):
    CALLS.append((method, url, body))
    u = urllib.parse.urlparse(url)
    if "oauth/v2/token" in u.path:
        return {"access_token": "tok", "expires_in": 3600}
    assert headers and headers["Authorization"] == "Zoho-oauthtoken tok"
    assert "organization_id=ORG" in u.query
    if u.path.endswith("/items"):
        return {"code": 0, "items": ITEMS, "page_context": {"has_more_page": False}}
    if u.path.endswith("/purchaseorders") and method == "GET":
        return {"code": 0, "purchaseorders": [{"purchaseorder_id": "P1"}], "page_context": {"has_more_page": False}}
    if u.path.endswith("/purchaseorders/P1"):
        return {"code": 0, "purchaseorder": {"line_items": [{"item_id": "I4", "quantity": 150, "quantity_received": 0},
                                                           {"item_id": "I13", "quantity": 400, "quantity_received": 100}]}}
    if u.path.endswith("/purchaseorders") and method == "POST":
        return {"code": 0, "purchaseorder": {"purchaseorder_id": "P9", "purchaseorder_number": "PO-0009", "status": "draft"}}
    raise AssertionError(url)

class T(unittest.TestCase):
    def setUp(self):
        _zoho._http = fake_http; _zoho._tok.update(v=None, exp=0); CALLS.clear()
        os.environ.update(ZOHO_CLIENT_ID="a", ZOHO_CLIENT_SECRET="b", ZOHO_REFRESH_TOKEN="c", ZOHO_ORG_ID="ORG",
                          ZOHO_DEFAULT_VENDOR_ID="V1")
        for k in ("ZOHO_SYNC_STOCK", "ZOHO_ALLOW_DRAFT_PO"): os.environ.pop(k, None)

    def test_open_po_nets_received(self):
        self.assertEqual(_zoho.open_po_units(), {"SKU004": 150, "SKU013": 300})

    def test_recommendations_use_open_orders(self):
        r = recommendations.build()
        by = {x["sku"]: x for x in r["results"]}
        self.assertEqual(r["sources"], {"stock": "csv", "open_orders": "zoho"})
        self.assertEqual(by["SKU004"]["status"], "OK")          # 180 on hand + 150 on order
        self.assertEqual(by["SKU011"]["status"], "REORDER_NOW")  # nothing on order

    def test_stock_sync(self):
        os.environ["ZOHO_SYNC_STOCK"] = "true"
        r = recommendations.build()
        self.assertEqual(r["sources"]["stock"], "zoho")
        self.assertEqual({x["sku"]: x["stock"] for x in r["results"]}["SKU002"], 200)

    def test_falls_back_to_csv_on_zoho_error(self):
        def boom(*a, **k): raise _zoho.ZohoError("down")
        _zoho._http = boom
        r = recommendations.build()
        self.assertEqual(r["sources"], {"stock": "csv", "open_orders": "csv"})
        self.assertEqual(r["zoho"]["error"], "down")
        self.assertEqual(len(r["results"]), 15)

    def test_draft_po_disabled_by_default(self):
        with self.assertRaises(_zoho.ZohoError): _zoho.create_draft_po("SKU004", 150, "data")

    def test_draft_po(self):
        os.environ["ZOHO_ALLOW_DRAFT_PO"] = "true"
        out = _zoho.create_draft_po("SKU004", 150, os.path.join(ROOT, "data"), "ref")
        self.assertEqual(out["purchaseorder_number"], "PO-0009")
        post = [c for c in CALLS if c[0] == "POST" and "purchaseorders" in c[1]][0]
        self.assertEqual(post[2]["line_items"], [{"item_id": "I4", "quantity": 150}])
        self.assertEqual(post[2]["vendor_id"], "V1")

    def test_not_configured_means_csv_only(self):
        os.environ.pop("ZOHO_ORG_ID")
        r = recommendations.build()
        self.assertEqual(r["sources"], {"stock": "csv", "open_orders": "csv"}); self.assertFalse(r["zoho"]["configured"])

if __name__ == "__main__":
    unittest.main()
