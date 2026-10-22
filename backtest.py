"""Replay the rules against the sales history and compare two planning cadences.

This is a SIMULATION, not a measurement of real outcomes: the seed has no historical
inventory, purchase orders or stockout records. Demand = recorded units sold (censored:
real demand during a past stockout is unknown). Assumptions are set in ASSUMPTIONS and
reported with the results.

Policies (both use the same rules from engine.decide):
  weekly  - runs every week on fresh sales and stock (what the tool enables)
  monthly - runs every 4 weeks on sales and stock that are DATA_LAG weeks old (today's process)

Usage: python3 backtest.py [--lead 2] [--out out]
"""
import argparse, csv, json
from datetime import date
from statistics import mean
from engine import decide, read, CONFIG

ASSUMPTIONS = {
    "lead_time_weeks": 2,      # order placed in week t arrives at the start of week t+lead
    "min_history_weeks": 8,    # seed has only 16 weeks; rules need 12, so replay starts with 8
    "monthly_every": 4,        # monthly policy decides every 4th week
    "data_lag_weeks": 3,       # case: data is 3-4 weeks old when procurement acts
    "start_cover": "midpoint of each SKU's safe window x avg of first weeks",
}

def week_is_festival(week, festival):
    y, w = int(week[:4]), int(week.split("W")[1])
    d = date.fromisocalendar(y, w, 1)
    return festival[f"{d.year}-{d.month:02d}"]

def simulate(policy, sku, vals, weeks, festival, lead, cfg=CONFIG):
    min_h, lag_w = ASSUMPTIONS["min_history_weeks"], ASSUMPTIONS["data_lag_weeks"]
    t0 = min_h + lag_w                 # both policies start on the same week, with the same stock
    perish = sku["Perishability"].lower() == "high"
    lo = cfg["perishable_min_weeks"] if perish else cfg["stockout_weeks"]
    hi = cfg["perishable_max_weeks"] if perish else cfg["overstock_weeks"]
    stock = (lo + hi) / 2 * mean(vals[:min_h])
    start_stock = stock
    on_order = {}                      # arrival week index -> qty
    stock_hist = {}                    # week index -> stock at start of that week
    lost = sold = orders = stockout_weeks = over_weeks = 0
    excess_units = cover_sum = 0.0
    n = len(vals)
    for t in range(t0, n):
        stock += on_order.pop(t, 0)
        stock_hist[t] = stock
        lag = 0 if policy == "weekly" else lag_w
        decide_now = policy == "weekly" or (t - t0) % ASSUMPTIONS["monthly_every"] == 0
        if decide_now and not any(a > t for a in on_order):
            x = t - lag
            seen = vals[:x]
            # stale stock: recorded if in the replay, else start stock plus what sold since (no arrivals before t0)
            seen_stock = stock_hist[x] if x in stock_hist else start_stock + sum(vals[x:t0])
            d = decide(sku, seen, round(seen_stock), week_is_festival(weeks[x], festival), cfg)
            if d["status"] in ("REORDER_NOW", "REORDER") and not d["review"]:
                on_order[t + lead] = d["qty"]; orders += 1
        demand = vals[t]
        s = min(stock, demand)
        sold += s; lost += demand - s
        if demand > stock: stockout_weeks += 1
        stock -= s
        rate = mean(vals[max(0, t - 11): t + 1])
        cover = stock / rate
        cover_sum += cover
        if cover > hi:
            over_weeks += 1; excess_units += stock - hi * rate
    weeks_n = n - t0
    return dict(lost_units=round(lost), sold_units=round(sold), stockout_weeks=stockout_weeks, overstock_weeks=over_weeks,
                excess_units=round(excess_units), avg_cover=round(cover_sum / weeks_n, 1), orders=orders)

def backtest(data_dir="data", lead=None):
    lead = lead or ASSUMPTIONS["lead_time_weeks"]
    skus = {r["SKU_ID"]: r for r in read(f"{data_dir}/sku_master.csv")}
    festival = {r["Year_Month"]: r["Is_Festival_Month"].upper() == "TRUE" for r in read(f"{data_dir}/calendar.csv")}
    series = {}
    for r in read(f"{data_dir}/weekly_sales.csv"):
        series.setdefault(r["SKU_ID"], {})[r["Week"]] = int(r["Units_Sold"])
    out = {}
    for sid, sku in skus.items():
        weeks = sorted(series[sid]); vals = [series[sid][w] for w in weeks]
        out[sid] = {p: simulate(p, sku, vals, weeks, festival, lead) for p in ("monthly", "weekly")}
        out[sid]["name"] = sku["SKU_Name"]; out[sid]["perishable"] = sku["Perishability"] == "High"
    return out

def totals(res, key):
    return {p: sum(r[p][key] for r in res.values()) for p in ("monthly", "weekly")}

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--lead", type=int); ap.add_argument("--out", default="out")
    a = ap.parse_args()
    res = backtest(lead=a.lead)
    lead = a.lead or ASSUMPTIONS["lead_time_weeks"]
    print(f"Lead time {lead} wks | replay weeks W38-W42 | policy comparison (all SKUs)")
    for k in ("lost_units", "stockout_weeks", "overstock_weeks", "excess_units", "orders"):
        t = totals(res, k); print(f"{k:<16} monthly={t['monthly']:<7} weekly={t['weekly']}")
    print("\nSensitivity (lost units, monthly -> weekly):")
    sens = {}
    for L in (1, 2, 3):
        r = backtest(lead=L); t = totals(r, "lost_units"); e = totals(r, "excess_units")
        sens[L] = dict(lost=t, excess=e)
        print(f"  lead {L}w: lost {t['monthly']} -> {t['weekly']} | excess {e['monthly']} -> {e['weekly']}")
    json.dump(dict(assumptions=ASSUMPTIONS, lead=lead, per_sku=res, sensitivity=sens), open(f"{a.out}/backtest.json", "w"), indent=1)
    with open(f"{a.out}/backtest.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["SKU", "Name", "Policy", "Lost_units", "Stockout_weeks", "Overstock_weeks", "Excess_units", "Avg_cover", "Orders"])
        for sid, r in res.items():
            for p in ("monthly", "weekly"):
                x = r[p]; w.writerow([sid, r["name"], p, x["lost_units"], x["stockout_weeks"], x["overstock_weeks"], x["excess_units"], x["avg_cover"], x["orders"]])
