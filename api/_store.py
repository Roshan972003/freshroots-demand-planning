"""Storage for accept/override decisions: Postgres (Neon) when DATABASE_URL is set, else a local SQLite file (dev only)."""
import os, sqlite3

DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
COLS = ("as_of", "sku", "decision", "rec_status", "rec_qty", "final_qty", "reason", "decided_at")

def _pg():
    import psycopg2
    return psycopg2.connect(DATABASE_URL)

def _sqlite():
    path = os.path.join(os.environ.get("TMPDIR", "/tmp"), "freshroots_overrides.db")
    return sqlite3.connect(path)

SCHEMA = """CREATE TABLE IF NOT EXISTS overrides (
    as_of TEXT NOT NULL, sku TEXT NOT NULL, decision TEXT NOT NULL, rec_status TEXT NOT NULL,
    rec_qty INTEGER NOT NULL, final_qty INTEGER, reason TEXT,
    decided_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (as_of, sku))"""

def _run(sql_pg, sql_lite, params=(), fetch=False):
    if DATABASE_URL:
        conn = _pg()
        try:
            with conn, conn.cursor() as cur:
                cur.execute(SCHEMA); cur.execute(sql_pg, params)
                return cur.fetchall() if fetch else None
        finally:
            conn.close()
    conn = _sqlite()
    try:
        with conn:
            conn.execute(SCHEMA); cur = conn.execute(sql_lite, params)
            return cur.fetchall() if fetch else None
    finally:
        conn.close()

def list_overrides(as_of):
    rows = _run("SELECT as_of,sku,decision,rec_status,rec_qty,final_qty,reason,decided_at::text FROM overrides WHERE as_of=%s",
                "SELECT as_of,sku,decision,rec_status,rec_qty,final_qty,reason,decided_at FROM overrides WHERE as_of=?",
                (as_of,), fetch=True)
    return [dict(zip(COLS, r)) for r in rows]

def save_override(as_of, sku, decision, rec_status, rec_qty, final_qty, reason):
    p = (as_of, sku, decision, rec_status, rec_qty, final_qty, reason)
    _run("""INSERT INTO overrides (as_of,sku,decision,rec_status,rec_qty,final_qty,reason) VALUES (%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (as_of,sku) DO UPDATE SET decision=EXCLUDED.decision, rec_status=EXCLUDED.rec_status,
            rec_qty=EXCLUDED.rec_qty, final_qty=EXCLUDED.final_qty, reason=EXCLUDED.reason, decided_at=now()::text""",
         """INSERT INTO overrides (as_of,sku,decision,rec_status,rec_qty,final_qty,reason) VALUES (?,?,?,?,?,?,?)
            ON CONFLICT (as_of,sku) DO UPDATE SET decision=excluded.decision, rec_status=excluded.rec_status,
            rec_qty=excluded.rec_qty, final_qty=excluded.final_qty, reason=excluded.reason, decided_at=CURRENT_TIMESTAMP""", p)

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
