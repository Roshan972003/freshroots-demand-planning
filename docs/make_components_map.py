"""Generates docs/components-map.svg: the Freshroots demand planning components map. Run: python3 docs/make_components_map.py"""
from xml.sax.saxutils import escape as esc

W = 1858
COLS = ["Trigger", "Input", "Rules", "Human", "Guard & memory", "Output"]
ROWS = [  # (name, subtitle, band colour)
    ("Planner", "(Raghav / Deepa)", "#dfe8f4"),
    ("Data files", "(CSV exports)", "#e6e0f0"),
    ("Zoho Inventory", "(real account, India)", "#f7efc9"),
    ("Rules engine", "(engine.py)", "#f8dbe6"),
    ("Dashboard", "(control tower)", "#dcecdc"),
    ("Approver", "(a named person)", "#d3ecec"),
    ("Approval gate", "(server check)", "#f8e3d3"),
    ("Neon database", "(Memory)", "#dfe8f4"),
    ("Procurement", "(a person)", "#e6e0f0"),
    ("Executive view", "(Reports)", "#e9e4dc"),
]
# colour kinds: people / app / service / data
KIND = {"people": ("#cfe0f6", "#4a86c8"), "app": ("#faeec0", "#d9a520"), "service": ("#cdeeee", "#2a9a9a"), "data": ("#f9d3e1", "#d9558a"), "safe": ("#cdeccf", "#3a9a4a")}
# id, row, col, kind, title, body lines
NODES = [
    (1, 0, 0, "people", "Opens the app", ["Dashboard on any device;", "run_weekly.sh gives a", "weekly CSV report"]),
    (2, 1, 1, "data", "Reads the data files", ["sales, SKU master, stock,", "calendar, festivals (CSV)"]),
    (3, 2, 1, "service", "Reads Zoho", ["stock + open POs, read-only,", "kept 45 s; falls back", "to the CSVs"]),
    (4, 3, 2, "app", "Applies the rules", ["4-vs-12-week, cover, perishable", "window, festival uplift by", "category or SKU; odd cases", "go to review"]),
    (5, 4, 3, "app", "Shows every flag", ["reasons, burn-down, what-if,", "festival plan, mid-week", "signals, distributor map"]),
    (6, 5, 3, "people", "Approves or overrides", ["a named person; reason tag;", "can become a 30-day rule"]),
    (7, 6, 4, "safe", "Checks the approval", ["no PO without a named", "approval of that SKU", "and quantity"]),
    (8, 7, 4, "service", "Saves everything", ["decisions, approvers, rules,", "uplifts, PO audit log"]),
    (9, 2, 5, "service", "Creates a draft PO", ["in Zoho as DRAFT only;", "the app never issues one"]),
    (10, 8, 5, "people", "Issues the PO", ["a person reviews the", "draft and issues it in Zoho"]),
    (11, 9, 5, "app", "Reports", ["12 metrics, summary, CEO", "report download, PO log"]),
]
EDGES = [  # from, to, label
    (1, 2, "reads"), (1, 3, "reads"), (2, 4, "data"), (3, 4, "stock + POs"), (4, 5, "flags"),
    (5, 6, "review"), (6, 7, "decision"), (7, 8, "logs"), (7, 9, "approved qty"), (9, 10, "draft"), (10, 11, "issued"),
]

X0, ACT_W, GAP = 92, 196, 7
COL_W = (W - 2 * 92 - ACT_W - GAP * 6) / 6.0
HDR_Y, HDR_H = 172, 62
ROW_Y0, ROW_H, ROW_GAP = 238, 142, 4
NODE_W, NODE_H = 214, 124
H = ROW_Y0 + len(ROWS) * (ROW_H + ROW_GAP) + 190

def colx(c): return X0 + ACT_W + GAP + c * (COL_W + GAP)
def rowy(r): return ROW_Y0 + r * (ROW_H + ROW_GAP)
def box(n):
    _, r, c, *_ = n
    x = colx(c) + (COL_W - NODE_W) / 2
    y = rowy(r) + (ROW_H - NODE_H) / 2
    return x, y, NODE_W, NODE_H
NB = {n[0]: box(n) for n in NODES}

o = []
o.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="Inter, Helvetica Neue, Helvetica, Arial, sans-serif">')
o.append('<defs><marker id="ar" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto"><path d="M0,0 L9,4.5 L0,9 z" fill="#4a4137"/></marker></defs>')
o.append(f'<rect width="{W}" height="{H}" fill="#e6edeb"/><rect x="58" y="28" width="{W-116}" height="{H-56}" rx="40" fill="#f7f4ea"/>')
o.append(f'<text x="{W/2}" y="104" text-anchor="middle" font-size="40" font-weight="800" fill="#2a2620">Freshroots Demand Planning · Components Map</text>')
o.append(f'<text x="{W/2}" y="140" text-anchor="middle" font-size="20" fill="#5a5247">Data and Zoho in → rules engine → a named human approves → draft PO in Zoho → a person issues it</text>')
o.append(f'<rect x="{X0}" y="{HDR_Y}" width="{ACT_W}" height="{HDR_H}" rx="14" fill="#655746"/><text x="{X0+ACT_W/2}" y="{HDR_Y+39}" text-anchor="middle" font-size="22" font-weight="700" fill="#fff">Actor</text>')
for i, cn in enumerate(COLS):
    o.append(f'<rect x="{colx(i)}" y="{HDR_Y}" width="{COL_W}" height="{HDR_H}" rx="14" fill="#655746"/><text x="{colx(i)+COL_W/2}" y="{HDR_Y+39}" text-anchor="middle" font-size="22" font-weight="700" fill="#fff">{esc(cn)}</text>')
for r, (name, sub, band) in enumerate(ROWS):
    y = rowy(r)
    o.append(f'<rect x="{X0}" y="{y}" width="{ACT_W}" height="{ROW_H}" rx="6" fill="#655746"/>')
    o.append(f'<text x="{X0+ACT_W/2}" y="{y+ROW_H/2-2}" text-anchor="middle" font-size="22" font-weight="700" fill="#fff">{esc(name)}</text>')
    o.append(f'<text x="{X0+ACT_W/2}" y="{y+ROW_H/2+24}" text-anchor="middle" font-size="15" fill="#e8dfd0">{esc(sub)}</text>')
    for c in range(6):
        o.append(f'<rect x="{colx(c)}" y="{y}" width="{COL_W}" height="{ROW_H}" rx="4" fill="{band}"/>')

def edge_path(a, b):
    ax, ay, aw, ah = NB[a]; bx, by, bw, bh = NB[b]
    if bx > ax + aw:                                   # to the right: out of the side, through the gutter, into the left side
        mx = (ax + aw + bx) / 2
        pts = [(ax + aw, ay + ah / 2), (mx, ay + ah / 2), (mx, by + bh / 2), (bx, by + bh / 2)]
    else:                                              # same column: straight down from bottom to top
        pts = [(ax + aw / 2, ay + ah), (bx + bw / 2, by)]
    return pts
pills = []
for a, b, label in EDGES:
    pts = edge_path(a, b)
    d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    o.append(f'<path d="{d}" fill="none" stroke="#4a4137" stroke-width="2" stroke-dasharray="7 5" marker-end="url(#ar)"/>')
    # put each label in a gap between two rows, so it never covers a node or its number badge
    if len(pts) == 4:                                  # right-going: vertical run in the gutter
        mx = pts[1][0]; y1, y2 = pts[1][1], pts[2][1]
        mid = (y1 + y2) / 2
        gaps = [rowy(r) + 144 for r in range(len(ROWS) - 1) if min(y1, y2) <= rowy(r) + 144 <= max(y1, y2)]
        py = min(gaps, key=lambda g: abs(g - mid)) if gaps else mid
        pills.append((mx, py, label))
    else:                                              # same column: straight down
        pills.append(((pts[0][0] + pts[1][0]) / 2, (pts[0][1] + pts[1][1]) / 2, label))

for n in NODES:
    i, r, c, kind, title, body = n
    x, y, w, h = NB[i]
    fill, stroke = KIND[kind]
    o.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w}" height="{h}" rx="16" fill="{fill}" stroke="{stroke}" stroke-width="3"/>')
    o.append(f'<circle cx="{x+4:.1f}" cy="{y+4:.1f}" r="15" fill="#2a2620"/><text x="{x+4:.1f}" y="{y+10:.1f}" text-anchor="middle" font-size="16" font-weight="700" fill="#fff">{i}</text>')
    o.append(f'<text x="{x+w/2:.1f}" y="{y+32:.1f}" text-anchor="middle" font-size="19" font-weight="800" fill="#2a2620">{esc(title)}</text>')
    for k, line in enumerate(body):
        o.append(f'<text x="{x+w/2:.1f}" y="{y+56+k*20:.1f}" text-anchor="middle" font-size="14" fill="#4a4137">{esc(line)}</text>')
for px, py, label in pills:
    tw = 16 + 7.6 * len(label)
    o.append(f'<rect x="{px-tw/2:.1f}" y="{py-11:.1f}" width="{tw:.1f}" height="22" rx="11" fill="#f7f4ea" stroke="#9a8f7e" stroke-width="1.5"/><text x="{px:.1f}" y="{py+5:.1f}" text-anchor="middle" font-size="14" font-weight="700" fill="#4a4137">{esc(label)}</text>')

ly = rowy(len(ROWS)) + 18
legend = [("data", "Data comes in"), ("app", "The app enforces the rules"), ("service", "Services store and read"), ("people", "People decide and act"), ("safe", "No PO without a named human")]
lx = 118
for kind, text in legend:
    fill, stroke = KIND[kind]; tw = 70 + 9.6 * len(text)
    o.append(f'<rect x="{lx}" y="{ly}" width="{tw:.0f}" height="58" rx="29" fill="{fill}" stroke="{stroke}" stroke-width="3"/><text x="{lx+tw/2:.0f}" y="{ly+37}" text-anchor="middle" font-size="19" fill="#2a2620">{esc(text)}</text>')
    lx += tw + 22
o.append(f'<text x="{W/2}" y="{ly+104}" text-anchor="middle" font-size="17" fill="#5a5247">Stack: plain HTML and JavaScript · Python functions on Vercel · Neon Postgres · Zoho Inventory API · GitHub</text>')
o.append(f'<text x="{W/2}" y="{ly+132}" text-anchor="middle" font-size="16" fill="#7a7062">Not connected: WhatsApp sending (the CS queue is sample data), a live SAP feed. The app never issues a PO; a person does.</text>')
o.append('</svg>')
open("docs/components-map.svg", "w").write("\n".join(o))
print("wrote docs/components-map.svg", W, "x", int(H))
