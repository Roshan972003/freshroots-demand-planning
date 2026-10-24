# 2-minute walkthrough

Live app: https://freshroots-demand-planning-indol.vercel.app

**1. The problem (15s).** Raghav plans monthly. His data is 3-4 weeks old when procurement acts, and errors cost ₹28–34L a quarter. His rules are sound but undocumented and slow to run.

**2. The overview (20s).** Open the app. The header shows the date, that stock and open POs come from Zoho, and a festival month (+25% demand uplift). At the last check the cards read 15 SKUs: 3 stockout risk, 2 overstock risk. Click a card to filter. (Almond Milk and Peanut Butter look fine because POs for them are already open in Zoho. That is the point of the Zoho link.)

**3. One flagged SKU (40s).** Click **Review** on **Multigrain Bread 400g**.
- It is perishable: 460 units, 1.8 weeks of cover against a 3-week minimum, so it is flagged "Reorder now" for 500.
- The rule inspector shows each step: the 4-week vs 12-week check, the festival uplift, the 3-4 week perishable window, and the final recommendation. The chart shows the last 12 weeks.
- Then show **Mango Drink**: sales are up 21% over the 12-week average, so the reorder is 1.5 x 500 = 750.

**4. The human in the loop (30s).** Set your name with the **Approver** button. On Multigrain Bread, click **Accept recommendation** (or override the quantity and pick a reason tag). Then **Select actionable** and **Execute batch POs**: the check always needs the "I approve" tick, and the server refuses any PO that has no named approval for that SKU and quantity. Explain: the system recommends, a named person approves, and a person issues the draft in Zoho. **Warning:** this creates real draft POs in your Zoho. Delete them afterwards, or stop at the check and press Cancel.

**5. Close (15s).** Quinoa shows 22 weeks of cover, so its next order is paused. Next step: the real backtest on three years of SAP history. The first replay on 16 weeks of data pointed the right way but is too thin to prove it.

**Before presenting:** clear any test overrides with the **Clear** button, so the override rate starts at "–".

## Added in the control-tower redesign
- **Festival toggle** (top right) re-runs the rules with the +25% uplift forced on or off, and **What-if** shifts demand from -50% to +50%. Both are simulations: decisions and POs are disabled until you reset.
- **Review** opens a slide-over with the reasons, the 12-week chart, a before/after cover preview, accept/override with reason tags (competitor scheme, distributor onboarding, unseasonal weather, trade promotion, new launch, distributor anomaly, other), and a draft-PO button.
- **Select actionable, then Accept & create draft POs** drafts POs for the selected SKUs in one go (demo sandbox unless real Zoho is connected). **Export proposals (CSV)** downloads the same list.

## Anomaly ticker, scheme alerts and burn-down
- **Ticker (under the header):** compares each region's latest week with its prior 4-week average. If a region moves more than 20%, it names the region and the open POs on that region's SKUs, and **Review & Hold Purchase Order** opens a drawer that logs a hold request for procurement (the tool never edits a PO). The seed has no real shift, so use **Simulate a Maharashtra -22% shift**; the alert is tagged SIMULATED.
- **Distributors table, Send Scheme Alert:** pick recipients, scheme name, expiry and target SKU, and see a WhatsApp-style preview. You can copy the message or download the recipient list. It does not send: that needs a WhatsApp Business API account.
- **Burn-down:** projected weeks of cover over 8 weeks for any SKU (default: a perishable at risk), with red, green and amber bands taken from that SKU's own thresholds. Dashed = no new order, solid = with the recommended order at an assumed lead time.

## Command menu, toasts, hotkeys, network map
- **Cmd/Ctrl+K** opens a command menu (filters, festival toggle, CSV export, draft POs, simulations, jump to a SKU). **J/K** move through rows, **A** approves, **E** edits, **P** pauses (logs a hold with a 10-second undo ring), **?** shows the cheat sheet.
- Toasts (bottom right) announce a mid-week anomaly or a churn-risk distributor. **Distributor network** is a schematic by region with health rings; a pulsing red ring is a distributor down 30%+ (use "Simulate churn" to see one). Click a node to open its panel and broadcast a scheme.

## Executive view, CS queue, gate, rules
- **Mandate banner:** day count, budget used and measured savings are typed in by a person (✎ buttons) and saved. Nothing there is measured automatically; savings read "Not measured yet" until someone enters a figure.
- **Executive dashboard:** 12 metrics computed from the data we have, an auto-generated three-line summary (rules, not an LLM) and a downloadable CEO report. Fulfilment rate, overstock value and complaints need SAP/WhatsApp data.
- **WhatsApp CS queue:** SAMPLE threads only, with SLA badges and an off-hours auto-responder setting. Nothing is sent: that needs the WhatsApp Business API.
- **Pre-flight gate (Execute batch POs):** compares Monday's snapshot with live signals (the mid-week regional shift). If demand differs by more than 10%, single-click approval is blocked and you must confirm the adjusted order.
- **Judgment capture:** overriding opens a modal for a reason tag and an optional switch that turns the override into a 30-day rule for that SKU's reorder quantity (removable).
- **Rule inspector:** each SKU's drawer shows the four logic steps (4-vs-12-week, festival uplift, perishability window, final recommendation) with one-click approval.

## Layout: tabs
The app is laid out as five tabs (Demand planning, Mid-week signals, WhatsApp CS desk, Executive view, What-if & burn-down) under a sticky header that carries the mandate strip. The Mid-week tab adds a Monday-snapshot vs live-signals comparison computed from the data. Command menu entries jump between tabs.

## Human approval for POs, and the Festival plan tab
- Set your name once with the **Approver** button in the header. Every decision and PO records it.
- **Festival plan:** shows the festival calendar, an editable uplift per category and per product, and which products rise most. Changing an uplift re-runs the rules and records who changed it.
- **Execute batch POs:** the check now always needs the "I approve" tick. Below the table, the audit log lists every PO raised and who approved it.
