# Data request: backtest for the demand planning tool

**To:** Freshroots IT team (cc: Deepa Nair, Raghav Kulkarni)
**Subject:** Data needed to validate the demand planning rules

Hi,

We have a first version of the demand planning tool running on a small sample (16 weeks of sales per SKU). Before anyone relies on it, we need to test Raghav's rules against what really happened. Could you export the following as CSV files?

1. **Weekly sales history, 3 years.** One row per SKU per week with units sold, ideally split by distributor. This is the data IT confirmed can be exported from SAP.
2. **Inventory history.** Weekly stock on hand per SKU and location for the same period. If snapshots don't exist, goods receipts and issues will do, so we can rebuild stock.
3. **Purchase orders from Zoho Inventory.** Order date, SKU, quantity, expected and actual delivery date. This also gives us supplier lead times, and lets us stop recommending reorders for stock that is already on its way.
4. **Stockout and write-off records.** Any list of SKUs that ran out before a delivery, and overstock written off, with dates and units or value. Even a rough list from Raghav or procurement helps.
5. **SKU prices or cost per unit**, so results can be shown in rupees and not only units.

**What we'll do with it:** replay the rules week by week and compare them with the actual stockouts and write-offs. The kill criterion is whether the rules would have prevented a meaningful share of them. We'll share the result with Raghav before anything goes further.

**Timing:** Ideally within a week, since the 90-day plan has a day-30 backtest checkpoint.

Thank you,
[Your name]
