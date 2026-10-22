"""Freshroots demand planning rules engine.

Encodes Raghav's documented rules (the ~80-85% that is rule-governed) and routes
everything else to a human review queue. Pure stdlib.

Usage: python3 engine.py [--month YYYY-MM] [--out out]
"""
import argparse, csv, json, os
from statistics import mean

CONFIG = {
    "baseline_weeks": 12,          # window for the average
    "recent_weeks": 4,             # window for the demand-spike check
    "spike_threshold": 0.20,       # recent4 > avg12 * 1.20 -> high demand
    "high_demand_multiplier": 1.5, # reorder at 1.5x standard qty
    "festival_uplift": 0.25,       # applied to demand rate before cover checks
    "stockout_weeks": 6, "overstock_weeks": 14,
    "perishable_min_weeks": 3, "perishable_max_weeks": 4,
    "max_inventory_age_days": 7,
}

def read(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))

def decide(s, vals, stock, is_fest, cfg=CONFIG):
    """Apply Raghav's rules to one SKU. s = sku_master row, vals = weekly units (oldest first)."""
    base = vals[-cfg["baseline_weeks"]:]
    recent = vals[-cfg["recent_weeks"]:]
    avg12, recent4 = mean(base), mean(recent)
    spike = recent4 / avg12 - 1
    rate = avg12 * (1 + cfg["festival_uplift"]) if is_fest else avg12
    cover = stock / rate
    perish = s["Perishability"].lower() == "high"
    lo = cfg["perishable_min_weeks"] if perish else cfg["stockout_weeks"]
    hi = cfg["perishable_max_weeks"] if perish else cfg["overstock_weeks"]
    std = int(s["Standard_Reorder_Qty"])

    flags = []
    high = spike > cfg["spike_threshold"]
    if high: flags.append("HIGH_DEMAND")
    if cover < lo: flags.append("STOCKOUT_RISK")
    if cover > hi: flags.append("OVERSTOCK_RISK")

    reasons, review = [], []
    if is_fest: reasons.append(f"Festival month: demand rate uplifted {cfg['festival_uplift']:.0%} ({avg12:.0f} -> {rate:.0f}/wk)")
    if high: reasons.append(f"Last 4 wks avg {recent4:.0f} is {spike:+.0%} vs 12-wk avg {avg12:.0f} (> +20%)")
    if "STOCKOUT_RISK" in flags: reasons.append(f"Cover {cover:.1f} wks < {lo} wk minimum")
    if "OVERSTOCK_RISK" in flags: reasons.append(f"Cover {cover:.1f} wks > {hi} wk maximum")
    if perish: reasons.append("High perishability: tight 3-4 wk window")

    qty, status, action = 0, "OK", "No action"
    if "STOCKOUT_RISK" in flags:
        status, action = "REORDER_NOW", "Immediate reorder"
        qty = round(std * (cfg["high_demand_multiplier"] if high else 1))
    elif high and "OVERSTOCK_RISK" not in flags:
        status, action = "REORDER", "Reorder at 1.5x standard qty"
        qty = round(std * cfg["high_demand_multiplier"])
    elif "OVERSTOCK_RISK" in flags and not high:
        status, action = "PAUSE_ORDER", "Pause next order"
    elif "OVERSTOCK_RISK" in flags and high:
        review.append("Conflicting signals: demand spike but overstocked")

    # Guard: a rule-driven order must not itself breach the overstock limit.
    if qty and (stock + qty) / rate > hi:
        review.append(f"Rule order of {qty} would push cover to {(stock+qty)/rate:.1f} wks (> {hi} max)")
    return dict(flags=flags, reasons=reasons, review=review, status=status, action=action, qty=qty,
                avg12=avg12, recent4=recent4, spike=spike, rate=rate, cover=cover,
                lo=lo, hi=hi, std=std, stock=stock, perish=perish)

def run(data_dir="data", month=None, cfg=CONFIG):
    sales = read(f"{data_dir}/weekly_sales.csv")
    skus = {r["SKU_ID"]: r for r in read(f"{data_dir}/sku_master.csv")}
    dists = {r["Distributor_ID"]: r for r in read(f"{data_dir}/distributor_master.csv")}
    inv = {r["SKU_ID"]: r for r in read(f"{data_dir}/current_inventory.csv")}
    festival = {r["Year_Month"]: r["Is_Festival_Month"].upper() == "TRUE" for r in read(f"{data_dir}/calendar.csv")}

    series = {}
    for r in sales:
        series.setdefault(r["SKU_ID"], {})[r["Week"]] = int(r["Units_Sold"])

    as_of = max(r["As_Of_Date"] for r in inv.values())
    month = month or as_of[:7]
    is_fest = festival.get(month)
    results = []
    for sid, s in skus.items():
        weeks = sorted(series.get(sid, {}))
        vals = [series[sid][w] for w in weeks]
        notes, review = [], []
        inv_row = inv.get(sid)
        d = dists.get(s["Distributor_ID"])
        if not vals: review.append("No sales history")
        if not inv_row: review.append("No inventory record")
        if len(vals) < cfg["baseline_weeks"]: review.append(f"Only {len(vals)} weeks of history (<{cfg['baseline_weeks']}) - new product?")
        if d is None or d["Status"] != "Active": review.append("Distributor missing or not active")
        if festival.get(month) is None: review.append(f"Month {month} not in calendar")
        if review and (not vals or not inv_row):
            results.append(dict(sku=sid, name=s["SKU_Name"], category=s["Category"], perishability=s["Perishability"],
                distributor=d["Distributor_Name"] if d else s["Distributor_ID"], status="REVIEW", action="Human review",
                flags=[], reasons=review, recommended_qty=0, stock=None, avg12=None, recent4=None, spike_pct=None,
                demand_rate=None, weeks_cover=None, min_weeks=None, max_weeks=None, weekly=[]))
            continue

        d_ = decide(s, vals, int(inv_row["Units_On_Hand"]), is_fest, cfg)
        flags, reasons, status, action, qty = d_["flags"], d_["reasons"], d_["status"], d_["action"], d_["qty"]
        avg12, recent4, spike, rate, cover = d_["avg12"], d_["recent4"], d_["spike"], d_["rate"], d_["cover"]
        lo, hi, std, stock, perish = d_["lo"], d_["hi"], d_["std"], d_["stock"], d_["perish"]
        review += d_["review"]

        age = (max_date(as_of) - max_date(inv_row["As_Of_Date"])).days
        if age > cfg["max_inventory_age_days"]: review.append(f"Inventory {age} days stale")

        if review:
            reasons += review
            status, action = "REVIEW", "Human review (Raghav)"
        results.append(dict(sku=sid, name=s["SKU_Name"], category=s["Category"], perishability=s["Perishability"],
            distributor=d["Distributor_Name"] if d else s["Distributor_ID"], status=status, action=action,
            flags=flags, reasons=reasons, recommended_qty=qty if status != "REVIEW" else 0,
            rule_qty=qty, stock=stock, avg12=round(avg12, 1), recent4=round(recent4, 1), spike_pct=round(spike*100, 1),
            demand_rate=round(rate, 1), weeks_cover=round(cover, 1), min_weeks=lo, max_weeks=hi,
            std_qty=std, weekly=list(zip(weeks, vals))))
    order = {"REORDER_NOW": 0, "REVIEW": 1, "REORDER": 2, "PAUSE_ORDER": 3, "OK": 4}
    results.sort(key=lambda r: (order[r["status"]], r["weeks_cover"] if r["weeks_cover"] is not None else 99))
    return dict(as_of=as_of, month=month, festival=bool(is_fest), config=cfg, results=results)

def max_date(s):
    from datetime import date
    return date.fromisoformat(s)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--month"); ap.add_argument("--data", default="data"); ap.add_argument("--out", default="out")
    a = ap.parse_args()
    res = run(a.data, a.month)
    os.makedirs(a.out, exist_ok=True)
    json.dump(res, open(f"{a.out}/recommendations.json", "w"), indent=1)
    with open(f"{a.out}/recommendations.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["SKU","Name","Status","Action","Reorder_Qty","Stock","Weeks_Cover","Flags","Reasons"])
        for r in res["results"]:
            w.writerow([r["sku"], r["name"], r["status"], r["action"], r["recommended_qty"], r["stock"], r["weeks_cover"], "|".join(r["flags"]), "; ".join(r["reasons"])])
    print(f"As of {res['as_of']} | month {res['month']} | festival={res['festival']}")
    for r in res["results"]:
        print(f"{r['sku']} {r['status']:<12} cover={r['weeks_cover']}  qty={r['recommended_qty']:<5} {r['name']}")
