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

def decide(s, vals, stock, is_fest, cfg=CONFIG, on_order=0, demand_adj=0.0, uplift=None):
    """Apply Raghav's rules to one SKU. s = sku_master row, vals = weekly units (oldest first).
    on_order = units already ordered but not yet received (counted as stock for the cover checks)."""
    base = vals[-cfg["baseline_weeks"]:]
    recent = vals[-cfg["recent_weeks"]:]
    avg12, recent4 = mean(base), mean(recent)
    spike = recent4 / avg12 - 1
    up = cfg["festival_uplift"] if uplift is None else uplift
    rate = avg12 * (1 + up) if is_fest else avg12
    rate *= 1 + demand_adj                       # what-if only; 0 in normal runs
    cover = (stock + on_order) / rate
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
    if is_fest: reasons.append(f"Festival month: demand rate uplifted {up:.0%} ({avg12:.0f} -> {avg12*(1+up):.0f}/wk)")
    if high: reasons.append(f"Last 4 wks avg {recent4:.0f} is {spike:+.0%} vs 12-wk avg {avg12:.0f} (> +20%)")
    if demand_adj: reasons.append(f"What-if: demand rate {demand_adj:+.0%}")
    if on_order: reasons.append(f"{on_order} units already on order are counted in stock")
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
    if qty and (stock + on_order + qty) / rate > hi:
        review.append(f"Rule order of {qty} would push cover to {(stock+on_order+qty)/rate:.1f} wks (> {hi} max)")
    return dict(flags=flags, reasons=reasons, review=review, status=status, action=action, qty=qty,
                avg12=avg12, recent4=recent4, spike=spike, rate=rate, cover=cover,
                lo=lo, hi=hi, std=std, stock=stock, perish=perish, on_order=on_order, uplift=up)

def find_anomalies(series, skus, dists, threshold=0.20, simulate=None, churn_threshold=0.30):
    """Latest week vs the mean of the prior 4 weeks, per region and per distributor (sums of their SKUs).
    simulate = ("region", "Maharashtra", 0.22) or ("dist", "DIST002", 0.35): scale that group's latest week so it
    sits `drop` below its 4-week mean. A labelled what-if, not real data."""
    vals_by_sku, region_of, dist_of = {}, {}, {}
    for sid, sku in skus.items():
        wk = sorted(series.get(sid, {}))
        v = [float(series[sid][w]) for w in wk]
        if len(v) < 5:
            continue
        vals_by_sku[sid] = v[-5:]
        dist_of[sid] = sku["Distributor_ID"]
        region_of[sid] = (dists.get(sku["Distributor_ID"]) or {}).get("Region", "Unknown")
    def total(sids):
        return [sum(vals_by_sku[s][i] for s in sids) for i in range(5)]
    if simulate:
        kind, name, drop = simulate
        group = [s for s in vals_by_sku if (region_of[s] if kind == "region" else dist_of[s]) == name]
        if group:
            t = total(group)
            k = (1 - drop) * mean(t[:-1]) / t[-1]
            for s in group:
                vals_by_sku[s][-1] *= k
    def chg(sids):
        t = total(sids)
        base = mean(t[:-1])
        return None if not base else dict(change_pct=round((t[-1] / base - 1) * 100, 1), latest=round(t[-1], 1), baseline=round(base, 1))
    regions, dist_list = [], []
    for region in sorted(set(region_of.values())):
        sids = [s for s in vals_by_sku if region_of[s] == region]
        c = chg(sids)
        if c and abs(c["change_pct"]) >= threshold * 100:
            regions.append(dict(region=region, skus=sids, **c))
    for did in sorted(set(dist_of.values())):
        sids = [s for s in vals_by_sku if dist_of[s] == did]
        c = chg(sids)
        if c:
            dist_list.append(dict(distributor_id=did, name=(dists.get(did) or {}).get("Distributor_Name", did),
                                  region=(dists.get(did) or {}).get("Region", "Unknown"), skus=sids,
                                  churn_risk=c["change_pct"] <= -churn_threshold * 100, **c))
    return dict(threshold_pct=threshold * 100, churn_threshold_pct=churn_threshold * 100, simulated=bool(simulate),
                simulation=simulate[1] if simulate else None, regions=regions, distributors=dist_list)

def run(data_dir="data", month=None, cfg=CONFIG, open_po=None, stock=None, today=None, festival=None, demand_adj=0.0, open_po_detail=None, simulate_shift=False, simulate_churn=False, sku_adj=None, rules=None, uplifts=None):
    sales = read(f"{data_dir}/weekly_sales.csv")
    skus = {r["SKU_ID"]: r for r in read(f"{data_dir}/sku_master.csv")}
    dists = {r["Distributor_ID"]: r for r in read(f"{data_dir}/distributor_master.csv")}
    inv = {r["SKU_ID"]: r for r in read(f"{data_dir}/current_inventory.csv")}
    festival_cal = {r["Year_Month"]: r["Is_Festival_Month"].upper() == "TRUE" for r in read(f"{data_dir}/calendar.csv")}
    fest_names = {}
    if os.path.exists(f"{data_dir}/festivals.csv"):
        fest_names = {r["Year_Month"]: r["Festival"] for r in read(f"{data_dir}/festivals.csv")}
    uplifts = uplifts or {}

    def uplift_for(sid, category):
        """Festival uplift for a SKU: its own override, else its category's, else Raghav's flat default."""
        if f"sku:{sid}" in uplifts:
            return uplifts[f"sku:{sid}"] / 100, "sku"
        if f"cat:{category}" in uplifts:
            return uplifts[f"cat:{category}"] / 100, "category"
        return cfg["festival_uplift"], "default"

    # Open purchase orders: passed in live (Zoho) or from data/open_orders.csv (SKU_ID, Quantity). Missing = nothing on order.
    po_source = "zoho" if open_po is not None else "csv"
    po_path = f"{data_dir}/open_orders.csv"
    if open_po is None:
        open_po = {}
    if po_source == "csv" and os.path.exists(po_path):
        csv_detail = []
        for r in read(po_path):
            open_po[r["SKU_ID"]] = open_po.get(r["SKU_ID"], 0) + int(float(r["Quantity"]))
            csv_detail.append(dict(po=r.get("PO_Number", ""), sku=r["SKU_ID"], qty=int(float(r["Quantity"]))))
        open_po_detail = csv_detail

    series = {}
    for r in sales:
        series.setdefault(r["SKU_ID"], {})[r["Week"]] = int(r["Units_Sold"])

    stock_source = "csv"
    if stock:                                   # live stock (Zoho) overrides the CSV for SKUs it returns
        stock_source = "zoho"
        for sid, u in stock.items():
            if sid in skus:
                inv[sid] = {"SKU_ID": sid, "Location": "Zoho", "Units_On_Hand": str(u), "As_Of_Date": today}
    as_of = max(r["As_Of_Date"] for r in inv.values())
    month = month or as_of[:7]
    calendar_fest = festival_cal.get(month)
    is_fest = calendar_fest if festival is None else festival
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
        if festival_cal.get(month) is None: review.append(f"Month {month} not in calendar")
        if review and (not vals or not inv_row):
            results.append(dict(sku=sid, name=s["SKU_Name"], category=s["Category"], perishability=s["Perishability"],
                distributor=d["Distributor_Name"] if d else s["Distributor_ID"], distributor_id=s["Distributor_ID"],
                region=d["Region"] if d else "Unknown", status="REVIEW", action="Human review",
                flags=[], reasons=review, recommended_qty=0, stock=None, avg12=None, recent4=None, spike_pct=None,
                demand_rate=None, weeks_cover=None, min_weeks=None, max_weeks=None, weekly=[]))
            continue

        up_sku, up_src = uplift_for(sid, s["Category"])
        d_ = decide(s, vals, int(inv_row["Units_On_Hand"]), is_fest, cfg, open_po.get(sid, 0), demand_adj + (sku_adj or {}).get(sid, 0.0), up_sku)
        flags, reasons, status, action, qty = d_["flags"], d_["reasons"], d_["status"], d_["action"], d_["qty"]
        avg12, recent4, spike, rate, cover = d_["avg12"], d_["recent4"], d_["spike"], d_["rate"], d_["cover"]
        lo, hi, std, stock, perish = d_["lo"], d_["hi"], d_["std"], d_["stock"], d_["perish"]
        review += d_["review"]
        rule = (rules or {}).get(sid)
        if rule and qty and status in ("REORDER_NOW", "REORDER"):     # temporary planner rule, e.g. from an override
            qty = max(0, round(qty * rule["ratio"]))
            reasons.append(f"Temporary planner rule ({rule['tag'] or 'no tag'}, until {rule['expires_at'][:10]}): quantity x{rule['ratio']:.2f}")

        age = (max_date(as_of) - max_date(inv_row["As_Of_Date"])).days
        if age > cfg["max_inventory_age_days"]: review.append(f"Inventory {age} days stale")

        if review:
            reasons += review
            status, action = "REVIEW", "Human review (Raghav)"
        results.append(dict(sku=sid, name=s["SKU_Name"], category=s["Category"], perishability=s["Perishability"],
            distributor=d["Distributor_Name"] if d else s["Distributor_ID"], distributor_id=s["Distributor_ID"],
            region=d["Region"] if d else "Unknown", status=status, action=action,
            flags=flags, reasons=reasons, recommended_qty=qty if status != "REVIEW" else 0,
            rule_qty=qty, planner_rule=rule, festival_uplift=round(up_sku * 100, 1), uplift_source=up_src, stock=stock, on_order=d_["on_order"], avg12=round(avg12, 1), recent4=round(recent4, 1), spike_pct=round(spike*100, 1),
            demand_rate=round(rate, 1), weeks_cover=round(cover, 1), min_weeks=lo, max_weeks=hi,
            std_qty=std, weekly=list(zip(weeks, vals))))
    # evidence for the festival plan: how each category has moved lately, and what uplift is in force
    cats = {}
    for r in results:
        if r.get("weekly") and len(r["weekly"]) >= 12:
            c = cats.setdefault(r["category"], dict(category=r["category"], skus=[], recent=0.0, prior=0.0))
            c["skus"].append(r["sku"]); v = [x[1] for x in r["weekly"]]
            c["recent"] += sum(v[-4:]) / 4; c["prior"] += sum(v[-12:-4]) / 8
    category_stats = []
    for name, c in sorted(cats.items()):
        sample = skus[c["skus"][0]]
        eff, src = uplift_for("", name)
        category_stats.append(dict(category=name, skus=c["skus"], observed_lift_pct=round((c["recent"] / c["prior"] - 1) * 100, 1) if c["prior"] else None,
                                   default_pct=round(cfg["festival_uplift"] * 100, 1), override_pct=uplifts.get(f"cat:{name}"), effective_pct=round(eff * 100, 1)))
    order = {"REORDER_NOW": 0, "REVIEW": 1, "REORDER": 2, "PAUSE_ORDER": 3, "OK": 4}
    results.sort(key=lambda r: (order[r["status"]], r["weeks_cover"] if r["weeks_cover"] is not None else 99))
    return dict(as_of=as_of, month=month, festival=bool(is_fest), calendar_festival=bool(calendar_fest), demand_adj=demand_adj,
                festival_name=fest_names.get(month, ""), calendar=festival_cal, festival_names=fest_names, category_stats=category_stats,
                config=cfg, results=results,
                sources=dict(stock=stock_source, open_orders=po_source), open_pos=open_po_detail or [],
                anomalies=find_anomalies(series, skus, dists, simulate=("region", "Maharashtra", 0.22) if simulate_shift else (("dist", "DIST002", 0.35) if simulate_churn else None)))

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
