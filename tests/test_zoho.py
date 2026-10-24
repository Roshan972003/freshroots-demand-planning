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
        recommendations._ZC.update(t=0.0, data=None)
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

class MockMode(unittest.TestCase):
    """ZOHO_MODE=mock exercises the real client code against the in-app simulated Zoho."""
    def setUp(self):
        recommendations._ZC.update(t=0.0, data=None)
        import importlib; importlib.reload(_zoho)
        for k in ("ZOHO_CLIENT_ID", "ZOHO_CLIENT_SECRET", "ZOHO_REFRESH_TOKEN", "ZOHO_ORG_ID", "ZOHO_SYNC_STOCK"): os.environ.pop(k, None)
        os.environ["ZOHO_MODE"] = "mock"; os.environ["ZOHO_ALLOW_DRAFT_PO"] = "true"
        os.environ["TMPDIR"] = "/tmp/zoho_mock_test"; os.makedirs("/tmp/zoho_mock_test", exist_ok=True)
        p = "/tmp/zoho_mock_test/freshroots_overrides.db"
        if os.path.exists(p): os.remove(p)
    def tearDown(self): os.environ.pop("ZOHO_MODE", None); os.environ.pop("ZOHO_ALLOW_DRAFT_PO", None)

    def test_open_pos_and_stock(self):
        import _store; _store.DATABASE_URL = None
        self.assertEqual(_zoho.open_po_units(), {"SKU004": 150, "SKU013": 300})   # billed PO ignored, received netted
        self.assertEqual(_zoho.stock_on_hand()["SKU004"], 180)

    def test_draft_po_roundtrip(self):
        import _store; _store.DATABASE_URL = None
        out = _zoho.create_draft_po("SKU011", 500, os.path.join(ROOT, "data"), "ref")
        self.assertEqual(out["status"], "draft")
        self.assertEqual(_zoho.open_po_units().get("SKU011"), None)   # drafts are not "open"
        r = recommendations.build()
        self.assertEqual(r["zoho"]["mode"], "demo")
        self.assertEqual({x["sku"]: x["status"] for x in r["results"]}["SKU004"], "OK")

class RealApiShapes(unittest.TestCase):
    """Behaviours taken from Zoho's documentation: missing stock field, purchaseorder_number retry, alternate wrapper key."""
    def setUp(self):
        recommendations._ZC.update(t=0.0, data=None)
        import importlib; importlib.reload(_zoho)
        os.environ.pop("ZOHO_MODE", None)
        os.environ.update(ZOHO_CLIENT_ID="a", ZOHO_CLIENT_SECRET="b", ZOHO_REFRESH_TOKEN="c", ZOHO_ORG_ID="ORG", ZOHO_DEFAULT_VENDOR_ID="V1", ZOHO_ALLOW_DRAFT_PO="true")
        os.environ.pop("ZOHO_SYNC_STOCK", None); _zoho._tok.update(v=None, exp=0); CALLS.clear()

    def test_missing_stock_field_falls_back_to_csv(self):
        os.environ["ZOHO_SYNC_STOCK"] = "true"
        no_stock = [{"item_id": i["item_id"], "sku": i["sku"]} for i in ITEMS]
        def http(method, url, headers=None, body=None):
            if url.endswith("items?organization_id=ORG&page=1&per_page=200") or "/items?" in url:
                return {"code": 0, "items": no_stock, "page_context": {"has_more_page": False}}
            return fake_http(method, url, headers, body)
        _zoho._http = http
        r = recommendations.build()
        self.assertEqual(r["sources"]["stock"], "csv")                  # not "zoho" with zero stock
        self.assertIn("stock_on_hand", r["zoho"]["error"])
        self.assertEqual({x["sku"]: x["stock"] for x in r["results"]}["SKU002"], 1200)

    def test_skips_draft_and_cancelled_and_reads_alternate_wrapper(self):
        def http(method, url, headers=None, body=None):
            u = urllib.parse.urlparse(url)
            if u.path.endswith("/purchaseorders") and method == "GET":
                return {"code": 0, "page_context": {"has_more_page": False}, "purchaseorders": [
                    {"purchaseorder_id": "D", "status": "draft"}, {"purchaseorder_id": "C", "status": "cancelled"}, {"purchaseorder_id": "P1", "status": "open"}]}
            if u.path.endswith("/purchaseorders/P1"):
                return {"code": 0, "purchase_order": {"purchaseorder_number": "PO-7", "line_items": [{"item_id": "I4", "quantity": 100, "quantity_received": 40}]}}
            if u.path.endswith("/purchaseorders/D") or u.path.endswith("/purchaseorders/C"):
                raise AssertionError("draft/cancelled POs must not be read")
            return fake_http(method, url, headers, body)
        _zoho._http = http
        self.assertEqual(_zoho.open_po_details(), [{"po": "PO-7", "sku": "SKU004", "qty": 60}])

    def test_po_number_retry(self):
        calls = []
        def http(method, url, headers=None, body=None):
            if method == "POST" and url.split("?")[0].endswith("/purchaseorders"):
                calls.append(body)
                if "purchaseorder_number" not in body:
                    return {"code": 4000, "message": "Please enter the purchase order number."}
                return {"code": 0, "purchase_order": {"purchaseorder_id": "P5", "purchaseorder_number": body["purchaseorder_number"], "status": "draft"}}
            return fake_http(method, url, headers, body)
        _zoho._http = http
        out = _zoho.create_draft_po("SKU004", 10, os.path.join(ROOT, "data"))
        self.assertEqual(len(calls), 2); self.assertTrue(out["purchaseorder_number"].startswith("DP-"))

    def test_bad_input_is_input_error(self):
        _zoho._http = fake_http
        with self.assertRaises(_zoho.ZohoInputError): _zoho.create_draft_po("NOPE", 5, "data")
        with self.assertRaises(_zoho.ZohoInputError): _zoho.create_draft_po("SKU004", 0, "data")


class Cache(unittest.TestCase):
    def setUp(self):
        import importlib; importlib.reload(_zoho)
        os.environ.pop("ZOHO_MODE", None)
        os.environ.update(ZOHO_CLIENT_ID="a", ZOHO_CLIENT_SECRET="b", ZOHO_REFRESH_TOKEN="c", ZOHO_ORG_ID="ORG", ZOHO_SYNC_STOCK="true")
        _zoho._tok.update(v=None, exp=0); CALLS.clear(); recommendations._ZC.update(t=0.0, data=None)
        _zoho._http = fake_http

    def test_second_read_comes_from_cache_and_fresh_bypasses_it(self):
        recommendations.build(); n = len(CALLS); self.assertGreater(n, 0)
        r = recommendations.build(); self.assertEqual(len(CALLS), n)                      # no new Zoho calls
        self.assertIn("cached_seconds", r["zoho"])
        recommendations.build(fresh=True); self.assertGreater(len(CALLS), n)              # forced refresh

    def test_zoho_failure_serves_last_good_read(self):
        recommendations.build()
        def boom(*a, **k): raise _zoho.ZohoError("down")
        _zoho._http = boom; _zoho._tok.update(v=None, exp=0)
        r = recommendations.build(fresh=True)
        self.assertIn("down", r["zoho"]["error"]); self.assertIn("ago", r["zoho"]["error"])
        self.assertEqual(r["sources"]["open_orders"], "zoho")                              # still the last good Zoho data
