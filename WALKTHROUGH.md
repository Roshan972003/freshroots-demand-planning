# 2-minute walkthrough

Live app: https://freshroots-demand-planning-indol.vercel.app

**1. The problem (15s).** Raghav plans monthly. His data is 3-4 weeks old when procurement acts, and errors cost ₹28–34L a quarter. His rules are sound but undocumented and slow to run.

**2. The overview (20s).** Open the app. The header shows inventory as of 19 Oct 2026 and a festival month (+25% demand uplift). The cards count the 15 SKUs: 5 reorder now, 2 pause, 8 OK, 0 needing review. Click a card to filter.

**3. One flagged SKU (40s).** Click **Almond Milk 500ml**.
- It is perishable: 180 units, 1.8 weeks of cover against a 3-week minimum, so it is flagged "Reorder now" for 150.
- The reasons list shows every rule that fired. The chart shows the last 12 weeks, the 12-week average and the last 4 weeks.
- Then show **Mango Drink**: sales are up 21% over the 12-week average, so the reorder is 1.5 x 500 = 750.

**4. The human in the loop (30s).** Back on Almond Milk, type a quantity (for example 200) and a reason, and click **Override**. The row gets an "overridden" tag and the **override rate** card updates. Click **Accept recommendation** on another SKU. Explain: the system never places an order. Raghav reviews, procurement orders, and the override rate tells us whether the rules match how he plans. If it passes about 40%, that is a kill signal.

**5. Close (15s).** Quinoa shows 22 weeks of cover, so its next order is paused. Next step: the real backtest on three years of SAP history. The first replay on 16 weeks of data pointed the right way but is too thin to prove it.

**Before presenting:** clear any test overrides with the **Clear** button, so the override rate starts at "–".

## Added in the control-tower redesign
- **Festival toggle** (top right) re-runs the rules with the +25% uplift forced on or off, and **What-if** shifts demand from -50% to +50%. Both are simulations: decisions and POs are disabled until you reset.
- **Review** opens a slide-over with the reasons, the 12-week chart, a before/after cover preview, accept/override with reason tags (competitor scheme, distributor onboarding, unseasonal weather, trade promotion, new launch, distributor anomaly, other), and a draft-PO button.
- **Select actionable, then Accept & create draft POs** drafts POs for the selected SKUs in one go (demo sandbox unless real Zoho is connected). **Export proposals (CSV)** downloads the same list.
