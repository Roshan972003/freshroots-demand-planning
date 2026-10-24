"""Storage for accept/override decisions: Postgres (Neon) when DATABASE_URL is set, else a local SQLite file (dev only)."""
import os, sqlite3

DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
COLS = ("as_of", "sku", "decision", "rec_status", "rec_qty", "final_qty", "reason", "tag", "decided_by", "decided_at")

def _pg():
    import psycopg2
    return psycopg2.connect(DATABASE_URL)

def _sqlite():
    path = os.path.join(os.environ.get("TMPDIR", "/tmp"), "freshroots_overrides.db")
    return sqlite3.connect(path)

SCHEMA = """CREATE TABLE IF NOT EXISTS overrides (
    as_of TEXT NOT NULL, sku TEXT NOT NULL, decision TEXT NOT NULL, rec_status TEXT NOT NULL,
    rec_qty INTEGER NOT NULL, final_qty INTEGER, reason TEXT, tag TEXT, decided_by TEXT,
    decided_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (as_of, sku))"""

def _run(sql_pg, sql_lite, params=(), fetch=False):
    if DATABASE_URL:
        conn = _pg()
        try:
            with conn, conn.cursor() as cur:
                cur.execute(SCHEMA); cur.execute("ALTER TABLE overrides ADD COLUMN IF NOT EXISTS tag TEXT"); cur.execute("ALTER TABLE overrides ADD COLUMN IF NOT EXISTS decided_by TEXT"); cur.execute(sql_pg, params)
                return cur.fetchall() if fetch else None
        finally:
            conn.close()
    conn = _sqlite()
    try:
        with conn:
            conn.execute(SCHEMA)
            cols = [c[1] for c in conn.execute("PRAGMA table_info(overrides)")]
            if "tag" not in cols:
                conn.execute("ALTER TABLE overrides ADD COLUMN tag TEXT")
            if "decided_by" not in cols:
                conn.execute("ALTER TABLE overrides ADD COLUMN decided_by TEXT")
            cur = conn.execute(sql_lite, params)
            return cur.fetchall() if fetch else None
    finally:
        conn.close()

def list_overrides(as_of):
    rows = _run("SELECT as_of,sku,decision,rec_status,rec_qty,final_qty,reason,tag,decided_by,decided_at::text FROM overrides WHERE as_of=%s",
                "SELECT as_of,sku,decision,rec_status,rec_qty,final_qty,reason,tag,decided_by,decided_at FROM overrides WHERE as_of=?",
                (as_of,), fetch=True)
    return [dict(zip(COLS, r)) for r in rows]

def save_override(as_of, sku, decision, rec_status, rec_qty, final_qty, reason, tag="", decided_by=""):
    p = (as_of, sku, decision, rec_status, rec_qty, final_qty, reason, tag, decided_by)
    _run("""INSERT INTO overrides (as_of,sku,decision,rec_status,rec_qty,final_qty,reason,tag,decided_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (as_of,sku) DO UPDATE SET decision=EXCLUDED.decision, rec_status=EXCLUDED.rec_status,
            rec_qty=EXCLUDED.rec_qty, final_qty=EXCLUDED.final_qty, reason=EXCLUDED.reason, tag=EXCLUDED.tag, decided_by=EXCLUDED.decided_by, decided_at=now()::text""",
         """INSERT INTO overrides (as_of,sku,decision,rec_status,rec_qty,final_qty,reason,tag,decided_by) VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT (as_of,sku) DO UPDATE SET decision=excluded.decision, rec_status=excluded.rec_status,
            rec_qty=excluded.rec_qty, final_qty=excluded.final_qty, reason=excluded.reason, tag=excluded.tag, decided_by=excluded.decided_by, decided_at=CURRENT_TIMESTAMP""", p)

def delete_override(as_of, sku):
    _run("DELETE FROM overrides WHERE as_of=%s AND sku=%s", "DELETE FROM overrides WHERE as_of=? AND sku=?", (as_of, sku))


# --- simulated Zoho (ZOHO_MODE=mock): draft purchase orders created through the demo sandbox -------------
MOCK_SCHEMA = """CREATE TABLE IF NOT EXISTS mock_pos (
    id TEXT PRIMARY KEY, vendor_id TEXT, reference TEXT, lines TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"""

def _run2(schema, sql_pg, sql_lite, params=(), fetch=False):
    if DATABASE_URL:
        conn = _pg()
        try:
            with conn, conn.cursor() as cur:
                cur.execute(schema); cur.execute(sql_pg, params)
                return cur.fetchall() if fetch else None
        finally:
            conn.close()
    conn = _sqlite()
    try:
        with conn:
            conn.execute(schema); cur = conn.execute(sql_lite, params)
            return cur.fetchall() if fetch else None
    finally:
        conn.close()

def save_mock_po(vendor_id, reference, lines):
    import json, time
    n = int(time.time() * 1000)
    po = {"purchaseorder_id": f"DEMO-DRAFT-{n}", "purchaseorder_number": f"PO-DEMO-D{n % 100000:05d}", "status": "draft",
          "vendor_name": vendor_id or "Demo Supplier", "line_items": lines}
    _run2(MOCK_SCHEMA, "INSERT INTO mock_pos (id, vendor_id, reference, lines) VALUES (%s,%s,%s,%s)",
          "INSERT INTO mock_pos (id, vendor_id, reference, lines) VALUES (?,?,?,?)",
          (po["purchaseorder_id"], vendor_id, reference, json.dumps(lines)))
    return po

def list_mock_pos():
    import json
    rows = _run2(MOCK_SCHEMA, "SELECT id, vendor_id, lines FROM mock_pos ORDER BY created_at",
                 "SELECT id, vendor_id, lines FROM mock_pos ORDER BY created_at", fetch=True)
    return [{"purchaseorder_id": r[0], "purchaseorder_number": "PO-" + r[0][-8:], "status": "draft",
             "vendor_name": r[1], "line_items": json.loads(r[2])} for r in rows]


# --- PO hold requests: a logged recommendation for procurement; the tool never edits POs in Zoho -----------
HOLD_SCHEMA = """CREATE TABLE IF NOT EXISTS po_holds (
    id TEXT PRIMARY KEY, po TEXT, sku TEXT, qty INTEGER, reason TEXT,
    requested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"""

def save_holds(rows, reason):
    import time
    n = int(time.time() * 1000)
    for i, r in enumerate(rows):
        _run2(HOLD_SCHEMA, "INSERT INTO po_holds (id, po, sku, qty, reason) VALUES (%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING",
              "INSERT OR IGNORE INTO po_holds (id, po, sku, qty, reason) VALUES (?,?,?,?,?)",
              (f"{n}-{i}", r["po"], r["sku"], int(r["qty"]), reason))

def list_holds():
    rows = _run2(HOLD_SCHEMA, "SELECT po, sku, qty, reason, requested_at::text FROM po_holds ORDER BY requested_at DESC LIMIT 50",
                 "SELECT po, sku, qty, reason, requested_at FROM po_holds ORDER BY requested_at DESC LIMIT 50", fetch=True)
    return [dict(zip(("po", "sku", "qty", "reason", "requested_at"), r)) for r in rows]


# --- temporary planner rules (30 days) and small shared settings -----------------------------------------------
RULE_SCHEMA = """CREATE TABLE IF NOT EXISTS planner_rules (
    sku TEXT PRIMARY KEY, ratio REAL NOT NULL, tag TEXT, reason TEXT, created_at TEXT NOT NULL, expires_at TEXT NOT NULL)"""
SET_SCHEMA = "CREATE TABLE IF NOT EXISTS app_settings (k TEXT PRIMARY KEY, v TEXT)"

def _now():
    import datetime
    return datetime.datetime.utcnow()

def save_rule(sku, ratio, tag, reason, days=30):
    import datetime
    a, b = _now(), _now() + datetime.timedelta(days=days)
    f = "%Y-%m-%d %H:%M:%S"
    _run2(RULE_SCHEMA, "INSERT INTO planner_rules (sku,ratio,tag,reason,created_at,expires_at) VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (sku) DO UPDATE SET ratio=EXCLUDED.ratio, tag=EXCLUDED.tag, reason=EXCLUDED.reason, created_at=EXCLUDED.created_at, expires_at=EXCLUDED.expires_at",
          "INSERT OR REPLACE INTO planner_rules (sku,ratio,tag,reason,created_at,expires_at) VALUES (?,?,?,?,?,?)",
          (sku, float(ratio), tag, reason, a.strftime(f), b.strftime(f)))

def list_rules():
    now = _now().strftime("%Y-%m-%d %H:%M:%S")
    rows = _run2(RULE_SCHEMA, "SELECT sku,ratio,tag,reason,created_at,expires_at FROM planner_rules WHERE expires_at > %s",
                 "SELECT sku,ratio,tag,reason,created_at,expires_at FROM planner_rules WHERE expires_at > ?", (now,), fetch=True)
    return {r[0]: dict(ratio=r[1], tag=r[2] or "", reason=r[3] or "", created_at=r[4], expires_at=r[5]) for r in rows}

def delete_rule(sku):
    _run2(RULE_SCHEMA, "DELETE FROM planner_rules WHERE sku=%s", "DELETE FROM planner_rules WHERE sku=?", (sku,))

def get_settings():
    rows = _run2(SET_SCHEMA, "SELECT k, v FROM app_settings", "SELECT k, v FROM app_settings", fetch=True)
    return {k: v for k, v in rows}

def set_setting(k, v):
    _run2(SET_SCHEMA, "INSERT INTO app_settings (k, v) VALUES (%s,%s) ON CONFLICT (k) DO UPDATE SET v=EXCLUDED.v",
          "INSERT OR REPLACE INTO app_settings (k, v) VALUES (?,?)", (k, v))


# --- festival uplift by category / SKU, and the purchase-order audit log ------------------------------------------
UPLIFT_SCHEMA = "CREATE TABLE IF NOT EXISTS festival_uplift (scope TEXT PRIMARY KEY, pct REAL NOT NULL, note TEXT, updated_by TEXT, updated_at TEXT NOT NULL)"
POLOG_SCHEMA = """CREATE TABLE IF NOT EXISTS po_log (
    id TEXT PRIMARY KEY, po_number TEXT, sku TEXT, qty INTEGER, as_of TEXT, approved_by TEXT, zoho_status TEXT, created_at TEXT NOT NULL)"""

def list_uplifts():
    rows = _run2(UPLIFT_SCHEMA, "SELECT scope, pct, note, updated_by, updated_at FROM festival_uplift", "SELECT scope, pct, note, updated_by, updated_at FROM festival_uplift", fetch=True)
    return {r[0]: dict(pct=r[1], note=r[2] or "", updated_by=r[3] or "", updated_at=r[4]) for r in rows}

def save_uplift(scope, pct, note, by):
    now = _now().strftime("%Y-%m-%d %H:%M:%S")
    _run2(UPLIFT_SCHEMA, "INSERT INTO festival_uplift (scope,pct,note,updated_by,updated_at) VALUES (%s,%s,%s,%s,%s) ON CONFLICT (scope) DO UPDATE SET pct=EXCLUDED.pct, note=EXCLUDED.note, updated_by=EXCLUDED.updated_by, updated_at=EXCLUDED.updated_at",
          "INSERT OR REPLACE INTO festival_uplift (scope,pct,note,updated_by,updated_at) VALUES (?,?,?,?,?)", (scope, float(pct), note, by, now))

def delete_uplift(scope):
    _run2(UPLIFT_SCHEMA, "DELETE FROM festival_uplift WHERE scope=%s", "DELETE FROM festival_uplift WHERE scope=?", (scope,))

def get_decision(as_of, sku):
    rows = _run2(SCHEMA, "SELECT decision, final_qty, decided_by FROM overrides WHERE as_of=%s AND sku=%s", "SELECT decision, final_qty, decided_by FROM overrides WHERE as_of=? AND sku=?", (as_of, sku), fetch=True)
    return dict(zip(("decision", "final_qty", "decided_by"), rows[0])) if rows else None

def log_po(po_number, sku, qty, as_of, approved_by, zoho_status):
    import time
    now = _now().strftime("%Y-%m-%d %H:%M:%S")
    _run2(POLOG_SCHEMA, "INSERT INTO po_log (id,po_number,sku,qty,as_of,approved_by,zoho_status,created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING",
          "INSERT OR IGNORE INTO po_log (id,po_number,sku,qty,as_of,approved_by,zoho_status,created_at) VALUES (?,?,?,?,?,?,?,?)",
          (f"{int(time.time()*1000)}-{sku}", po_number, sku, int(qty), as_of, approved_by, zoho_status, now))

def list_po_log():
    rows = _run2(POLOG_SCHEMA, "SELECT po_number,sku,qty,as_of,approved_by,zoho_status,created_at FROM po_log ORDER BY created_at DESC LIMIT 50",
                 "SELECT po_number,sku,qty,as_of,approved_by,zoho_status,created_at FROM po_log ORDER BY created_at DESC LIMIT 50", fetch=True)
    return [dict(zip(("po_number", "sku", "qty", "as_of", "approved_by", "zoho_status", "created_at"), r)) for r in rows]
