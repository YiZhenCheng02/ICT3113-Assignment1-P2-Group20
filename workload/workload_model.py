"""
workload_model.py
Reproduces every number in workload_model.md from the CFPB export of Capital One complaints.

Usage:
    python workload_model.py complaints-2026-10-07_13_39.csv ../golden_set/team20_rows_20000_20999.csv
    (the 2nd file is optional - it adds the ticket length statistics for Section 4)

The export's "Date received" is a UTC timestamp (e.g. 2025-10-08T00:35:05Z).
We report hour-of-day in BOTH UTC and US Eastern time (most of Capital One's customers are in the US).
"""
import sys
import pandas as pd

SEARCHES_PER_TICKET = 1.5   # [E] 1 search per ticket + 1 extra for 50% of tickets
SURGE_FACTOR = 3            # [E] incident day vs observed peak hour (see TSB 2018 outage)

d = pd.read_csv(sys.argv[1])
utc = pd.to_datetime(d["Date received"], utc=True)
et = utc.dt.tz_convert("America/New_York")

# ---- 1. Volume (team's figures) ----------------------------------------
n, days = len(d), 362
print(f"Complaints: {n:,}  | first {utc.min()}  last {utc.max()}  | window {days} days")
print(f"Annual  = {n} / {days} x 365 = {n / days * 365:,.0f}   (team rounds to ~33,739 / ~33,700)")
print(f"Per day = {n} / {days}       = {n / days:.1f}      (team rounds to ~93)")
monthly = et.dt.tz_localize(None).dt.to_period("M").value_counts().sort_index()
print("Monthly counts:", {str(k): int(v) for k, v in monthly.items()})

# ---- 2. Hourly arrival rate: build the full Date x Hour grid ---------------
# Step 1 of the method: every hour of all 362 days gets its own row, including hours with
# 0 complaints -> 362 x 24 = 8,688 rows. The grid runs from 8 Oct 2025 00:00 to 4 Oct 2026 23:00 (UTC),
# because the CFPB timestamps are in UTC.
hours = utc.dt.floor("h")
grid = pd.date_range("2025-10-08 00:00", periods=days * 24, freq="h", tz="UTC")
per_hour = hours.value_counts().reindex(grid, fill_value=0)

# Save the grid so anyone can check it in Excel (columns: Date, Hour of the Day, Number of Complaints)
et_grid = grid.tz_convert("America/New_York")
pd.DataFrame({
    "Date (UTC)": grid.date, "Hour of the Day (UTC)": grid.hour,
    "Date (US Eastern)": et_grid.date, "Hour of the Day (US Eastern)": et_grid.hour,
    "Number of Complaints": per_hour.values,
}).to_csv("hourly_counts.csv", index=False)
print(f"\nSaved hourly_counts.csv: {len(per_hour):,} rows (= {days} days x 24 hours)")

# Steps 2-4 of the method: for EACH hour of the day, take its 362 values, sort them and take the
# middle value (with an even count, the average of the 181st and 182nd values = the median).
for label, idx in [("UTC", grid), ("US Eastern", et_grid)]:
    by_hod = pd.Series(per_hour.values, index=idx.hour).groupby(level=0)
    table = pd.DataFrame({"n": by_hod.size(), "median": by_hod.median(), "mean": by_hod.mean().round(1),
                          "p95": by_hod.quantile(.95), "max": by_hod.max()})
    table.index.name = f"hour ({label})"
    print(f"\nPer hour-of-day statistics ({label}) - median of the {days} values for each hour:")
    print(table.to_string())
# Note: in US Eastern time some hours have 361 or 363 values instead of 362 because of the
# daylight-saving switches (Nov 2025, Mar 2026). This is expected.
print(f"\nHourly arrivals over {len(per_hour):,} hours: mean {per_hour.mean():.2f}, median {per_hour.median():.0f}, "
      f"p95 {per_hour.quantile(.95):.0f}, p99 {per_hour.quantile(.99):.0f}, max {per_hour.max()} "
      f"(at {per_hour.idxmax().tz_convert('America/New_York')} ET)")

et_idx = per_hour.index.tz_convert("America/New_York")
business = (et_idx.dayofweek < 5) & (et_idx.hour >= 9) & (et_idx.hour < 18)
print(f"Weekday 09:00-18:00 ET hours: mean {per_hour[business].mean():.1f}, median {per_hour[business].median():.0f}, p95 {per_hour[business].quantile(.95):.0f}")
print(f"All other hours (nights/weekends): mean {per_hour[~business].mean():.1f}, median {per_hour[~business].median():.0f}")

# ---- 3. When is it busy? -------------------------------------------------
for label, t in [("UTC", utc), ("US Eastern", et)]:
    hod = t.dt.hour.value_counts().sort_index() / days
    print(f"\nAverage tickets per hour-of-day ({label}):")
    print("  " + " ".join(f"{h:02d}:{v:.1f}" for h, v in hod.items()))

per_day = et.dt.date.value_counts().sort_index()
dow = pd.Series(per_day.values, index=pd.to_datetime(per_day.index).day_name())
order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
print("\nAverage tickets per day of week (ET):", dow.groupby(level=0).mean().round(1).reindex(order).to_dict())
print(f"Weekday share of volume: {dow[~dow.index.isin(['Saturday', 'Sunday'])].sum() / dow.sum():.1%}")
print(f"Busiest day: {per_day.idxmax()} with {per_day.max()} tickets")

# ---- 4. Load levels + searches ----------------------------------------------
levels = [("Non-peak (typical hour, mean)", round(per_hour.mean())),
          ("High (p95 hour)", per_hour.quantile(.95)),
          ("Peak (max observed hour)", per_hour.max()),
          ("Surge (3 x peak) [E]", per_hour.max() * SURGE_FACTOR)]
print("\nLoad levels:")
for name, t in levels:
    s = t * SEARCHES_PER_TICKET
    print(f"  {name:<32} {t:5.0f} tickets/h = {t / 60:.2f}/min | {s:5.1f} searches/h = {s / 60:.2f}/min")

# ---- 5. Product mix (Capital One) ------------------------------------------
print("\nProduct mix:", (d["Product"].value_counts(normalize=True) * 100).round(1).to_dict())
print("Submitted via:", d["Submitted via"].value_counts().to_dict())

# ---- 6. Ticket length distribution (Section 4) - optional 2nd argument -----------
# python workload_model.py complaints-....csv ../golden_set/team20_rows_20000_20999.csv
if len(sys.argv) > 2:
    rows = pd.read_csv(sys.argv[2])
    words = rows["narrative"].str.split().str.len()
    chars = rows["narrative"].str.len()
    print(f"\nTicket lengths ({len(rows)} rows, {rows['row'].min()}-{rows['row'].max()}):")
    bins = pd.cut(words, [0, 100, 250, 500, 1000, float("inf")],
                  labels=["0-100", "101-250", "251-500", "501-1,000", ">1,000"])
    print("  Word-count bins:", bins.value_counts().sort_index().to_dict())
    for name, s in [("Words", words), ("Characters", chars)]:
        print(f"  {name:<10} mean {s.mean():.1f}, min {s.min()}, median {s.median():.0f}, "
              f"p90 {s.quantile(.9):.0f}, p95 {s.quantile(.95):.0f}, p99 {s.quantile(.99):.0f}, max {s.max()}")