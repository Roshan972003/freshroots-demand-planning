"""End-to-end tests of the human-in-the-loop rules and festival uplift, through the real handlers (dev server routing).
Run: python3 -m unittest tests.test_hitl -v"""
import json, os, sys, tempfile, threading, unittest, urllib.error, urllib.request
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "api"))
TMP = tempfile.mkdtemp()
os.environ.update(TMPDIR=TMP, ZOHO_MODE="mock", ZOHO_ALLOW_DRAFT_PO="true")
for k in ("DATABASE_URL", "POSTGRES_URL", "ZOHO_SYNC_STOCK"): os.environ.pop(k, None)
import _store; _store.DATABASE_URL = None
from http.server import ThreadingHTTPServer
import dev

def call(port, method, path, body=None):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r: return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e: return e.code, json.loads(e.read() or b"{}")

class T(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import importlib, _zoho                      # other test modules change Zoho state; start from a clean one
        os.environ.update(TMPDIR=TMP, ZOHO_MODE="mock", ZOHO_ALLOW_DRAFT_PO="true")
        for k in ("ZOHO_CLIENT_ID", "ZOHO_CLIENT_SECRET", "ZOHO_REFRESH_TOKEN", "ZOHO_ORG_ID", "ZOHO_SYNC_STOCK"): os.environ.pop(k, None)
        importlib.reload(_zoho); _store.DATABASE_URL = None
        import recommendations; recommendations._ZC.update(t=0.0, data=None)
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), dev.Dev); cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
    @classmethod
    def tearDownClass(cls): cls.srv.shutdown()

    def test_decision_needs_a_named_person(self):
        s, j = call(self.port, "POST", "/api/overrides", {"as_of": "T", "sku": "SKU011", "decision": "accepted", "rec_qty": 500})
        self.assertEqual(s, 400); self.assertIn("decided_by", j["error"])

    def test_po_refused_without_approver_decision_or_matching_qty(self):
        p = self.port
        self.assertEqual(call(p, "POST", "/api/zoho_po", {"sku": "SKU011", "qty": 500, "as_of": "T1"})[0], 403)                     # no approver
        s, j = call(p, "POST", "/api/zoho_po", {"sku": "SKU011", "qty": 500, "as_of": "T1", "approver": "Asha"})
        self.assertEqual(s, 403); self.assertIn("no human approval", j["error"])                                                    # no decision
        call(p, "POST", "/api/overrides", {"as_of": "T1", "sku": "SKU011", "decision": "accepted", "rec_qty": 500, "rec_status": "REORDER_NOW", "decided_by": "Asha"})
        s, j = call(p, "POST", "/api/zoho_po", {"sku": "SKU011", "qty": 900, "as_of": "T1", "approver": "Asha"})
        self.assertEqual(s, 403); self.assertIn("differs", j["error"])                                                              # other quantity
        s, j = call(p, "POST", "/api/zoho_po", {"sku": "SKU011", "qty": 500, "as_of": "T1", "approver": "Asha"})
        self.assertEqual(s, 200); self.assertEqual(j["status"], "draft")                                                            # approved: a DRAFT only
        log = call(p, "GET", "/api/po_log")[1]
        self.assertTrue(any(x["sku"] == "SKU011" and x["approved_by"] == "Asha" and x["qty"] == 500 for x in log))

    def test_override_quantity_is_what_gets_ordered(self):
        p = self.port
        call(p, "POST", "/api/overrides", {"as_of": "T2", "sku": "SKU001", "decision": "overridden", "rec_qty": 750, "final_qty": 600, "tag": "New launch", "decided_by": "Raghav"})
        self.assertEqual(call(p, "POST", "/api/zoho_po", {"sku": "SKU001", "qty": 750, "as_of": "T2", "approver": "Raghav"})[0], 403)
        self.assertEqual(call(p, "POST", "/api/zoho_po", {"sku": "SKU001", "qty": 600, "as_of": "T2", "approver": "Raghav"})[0], 200)

    def test_festival_uplift_by_category_changes_demand(self):
        p = self.port
        base = call(p, "GET", "/api/recommendations")[1]
        mango = lambda d: next(r for r in d["results"] if r["sku"] == "SKU001")
        self.assertEqual(mango(base)["festival_uplift"], 25.0)
        self.assertEqual(call(p, "POST", "/api/uplift", {"scope": "cat:Beverage", "pct": 40})[0], 400)                              # needs a person
        self.assertEqual(call(p, "POST", "/api/uplift", {"scope": "cat:Beverage", "pct": 400, "by": "Asha"})[0], 400)               # out of range
        self.assertEqual(call(p, "POST", "/api/uplift", {"scope": "cat:Beverage", "pct": 40, "by": "Asha"})[0], 200)
        after = call(p, "GET", "/api/recommendations")[1]
        self.assertEqual(mango(after)["festival_uplift"], 40.0); self.assertEqual(mango(after)["uplift_source"], "category")
        self.assertGreater(mango(after)["demand_rate"], mango(base)["demand_rate"])
        snack = next(r for r in after["results"] if r["sku"] == "SKU002"); self.assertEqual(snack["festival_uplift"], 25.0)         # other categories unchanged
        call(p, "POST", "/api/uplift", {"scope": "sku:SKU001", "pct": 10, "by": "Asha"})
        self.assertEqual(mango(call(p, "GET", "/api/recommendations")[1])["uplift_source"], "sku")                                  # product beats category
        call(p, "DELETE", "/api/uplift?scope=sku:SKU001"); call(p, "DELETE", "/api/uplift?scope=cat:Beverage")
        self.assertEqual(mango(call(p, "GET", "/api/recommendations")[1])["festival_uplift"], 25.0)

if __name__ == "__main__":
    unittest.main()
