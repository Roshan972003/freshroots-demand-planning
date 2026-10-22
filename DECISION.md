# Demand Planning: Nine Checks and Five Pre-Build Decisions

Freshroots, Deepa's 90-day mandate. This document covers Demand Planning only.

Live app: https://freshroots-demand-planning-indol.vercel.app

**Verdict: build it. The system recommends, Raghav reviews, procurement places the order. The engine never places a purchase order.**

## 1. Nine Checks

| Group | Rule |
|---|---|
| Kill Switches (01-03) | Any No means don't build it. |
| Sizing (04, 05, 08) | Any No means build something smaller. |
| Boundary (06, 07, 09) | Any No means put a human exactly there. |

| # | Check | Answer | Evidence |
|---|---|---|---|
| 01 | Problem real? | **YES** | Stockouts cost ₹18–22L a quarter and overstock write-offs ₹10–12L, so ₹28–34L a quarter in total. The cost is measurable. |
| 02 | Workflow repeated? | **YES** | Raghav repeats the SAP-to-Excel forecast every month for 400 SKUs across 1,200 distributors. |
| 03 | Input available? | **YES** | Three years of sales in SAP, exportable as structured files. Inventory and Zoho purchase orders exist. The seed files ran through the engine end to end. |
| 04 | Output valuable? | **YES** | A status, order quantity and reasons per SKU replace about two days of Excel work. |
| 05 | Impact measurable? | **YES** | Baseline in rupees and cycle time (see section 2). |
| 06 | Failure risk OK? | **YES** for recommending, **NO** for auto-ordering | A wrong order costs money and perishables can't be returned. A recommendation can be checked before it is acted on. |
| 07 | Judgment protected? | **YES** | Raghav's rules cover 80–85% of decisions. The other 15–20% (launches, odd distributor behaviour, one-off events) go to a review queue for him. |
| 08 | ROI worth it? | **YES** | The whole budget is ₹15L against a loss of ₹28–34L a quarter. It pays back inside a quarter if it removes about half the loss. That capture rate is an assumption until the backtest. |
| 09 | Owner clear? | **YES** for recommendations, **NO** for auto-ordering | Raghav owns the recommendations and procurement owns the orders. Nobody is accountable for a system-placed purchase order. |

**What the two Boundary Nos mean:** put a human exactly at order placement. That is how it is built.

## 2. Five Pre-Build Decisions

**1. Outcome definition: what improvement, for whom, measured how?**
Fewer stockouts and fewer overstock write-offs, for procurement and the CEO. Measured as lost-sales lakhs and write-off lakhs per quarter, from SAP and Zoho. Secondary: Raghav's forecast cycle moves from monthly to twice a week.

**2. Baseline: what does the current state look like in numbers?**
- ₹28–34L a quarter lost (₹18–22L lost sales + ₹10–12L write-offs)
- monthly forecast cycle
- about 2 working days of Raghav's prep a month
- data 3–4 weeks old by the time procurement acts
- documented rules cover 80–85% of recommendations
- *To record on the first run:* last quarter's actual stockout and write-off figures from SAP and Zoho, so the 90-day comparison uses real numbers.

**3. Workflow change: what human process must change for the tool to work?**
- IT drops a fresh SAP sales export and inventory export into `data/` twice a week.
- Raghav reviews the output and the review queue instead of building the forecast.
- Procurement orders from the recommendations (a human places every order).
- Raghav's overrides are logged, so the rules can be improved.

**4. Measurement plan: how will you know in 90 days if it worked?**
Weekly tracking:
- stockout incidents and the lost-sales estimate
- overstock value and write-offs
- forecast cycle time (target: twice a week)
- recommendation override rate
- size of the review queue

Milestones (proposed):
- **Day 30:** Backtest the thresholds on three years of history. The engine should have caught known stockouts and overstocks. Then go live in shadow mode next to Raghav's forecast.
- **Day 60:** Compare the engine's recommendations with Raghav's on the same weeks.
- **Day 90:** Compare the quarter's stockout and write-off lakhs with the baseline. Target: halve the loss (proposed, for Deepa to confirm).

**5. Kill criterion: at what point do you shut it down?**
Proposed, with thresholds for Deepa to confirm. Shut it down, or go back and rebuild, if any of these hold:
- the day-30 backtest shows the rules would not have prevented a meaningful share of past stockouts or overstock
- Raghav overrides more than about 40% of recommendations at day 60, which means the rules don't match how he plans
- IT can't deliver the twice-weekly export by day 30, because the cycle-time gain disappears
- stockout and write-off lakhs are not improving against the baseline by day 90

## 3. What was built

- `engine.py` encodes Raghav's rules (spike, stockout, overstock, festival uplift, perishable window) and the review-queue triggers.
- `out/dashboard.html` shows status, cover and reasoning for each SKU.
- `run_weekly.sh` refreshes the outputs and archives each run.
- On 19 Oct 2026 (a festival month) it flags 5 SKUs for reorder now, 2 to pause and 8 as fine.

## 4. Risks and open items

- **Real backtest not done yet.** A first replay on the 16-week seed (see `BACKTEST.md`) points the right way but is too thin to test the kill criterion. The thresholds are Raghav's, not tuned.
- **Data gaps:** the seed is per-SKU weekly (the case describes distributor-level data), there is one warehouse, and open Zoho purchase orders aren't netted off stock.
- **Targets are proposals.** The 50% loss reduction and the 40% override limit are mine, not the case's.
- **Adoption:** Raghav must see the engine as helping him. Every flag shows its reasons.
