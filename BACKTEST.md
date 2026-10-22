# Backtest: rules replayed against the sales history

Run with `python3 backtest.py` (`--lead 1|2|3` for lead time). Outputs: `out/backtest.csv`, `out/backtest.json`.

## What it does
Replays the engine's rules (the same `decide()` the dashboard uses) over the recorded weekly sales and compares two cadences:
- **Weekly** (what the tool enables): decides every week on fresh sales and stock.
- **Monthly** (today's process): decides every 4 weeks on sales and stock that are 3 weeks old.

## Result (lead time 2 weeks, replay weeks W38-W42, 15 SKUs)

| | Monthly | Weekly |
|---|---|---|
| Units lost to stockouts | 713 | 425 |
| Stockout SKU-weeks | 6 | 4 |
| Overstock SKU-weeks | 0 | 0 |

Sensitivity to the lead time assumption (units lost, monthly to weekly):
- 1 week: 713 to 105
- 2 weeks: 713 to 425
- 3 weeks: 713 to 713 (no difference)

Only three SKUs lose any sales: Almond Milk (SKU004), Coconut Water (SKU007) and Multigrain Bread (SKU011). Weekly helps on two of them. Coconut Water is identical under both. The other 12 SKUs lose nothing under either cadence.

## What this does and does not show
**It shows** the direction the case predicts: running the same rules more often cuts stockouts on the fast-moving perishables, and the benefit shrinks as the supplier lead time grows. The rules didn't cause overstock in the replay.

**It does not validate the kill criterion.** The comparison is too thin to rely on:
- The seed has only 16 weeks of sales per SKU, not three years. The rules need 12 weeks of history, so the replay starts with 8 and covers 5 weeks (W38-W42).
- There is no historical inventory, no purchase orders and no recorded stockouts. Starting stock is an assumption (the midpoint of each SKU's safe window), and it drives most of the result. Lost sales are measured against recorded units sold, which understates demand wherever a past stockout occurred.
- Lead time is an assumption. The case doesn't give one, and the result swings from a large gain to none across 1 to 3 weeks.
- The monthly policy only gets two decision points in the window, and the second one's order arrives after the replay ends.
- Units, not rupees, since the data has no prices.

## What is needed for the real day-30 backtest
1. The three years of SAP sales history the case says exists (the seed has 16 weeks).
2. Historical inventory snapshots or purchase orders from Zoho, so stock can be reconstructed.
3. Actual stockout and write-off records, to compare the engine against what really happened.
4. Supplier lead times per SKU.
