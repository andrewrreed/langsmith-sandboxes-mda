---
name: dashboard
description: Build or update a dashboard (KPIs, charts, optional forecast) as a single HTML file from data in the sandbox, and share it.
---

# Build a dashboard

Use this when the user asks for a dashboard or report, or to add something (like a forecast) to an existing one.

## Data

- Save each query result to `/workspace/data/<name>.csv` (header + rows only). Write all CSVs and the script in one batch of parallel `write_file` calls.
- On follow-up turns, reuse the CSVs and the script already in the sandbox instead of querying Snowflake again, unless the user asks for new data. Edit `/workspace/dashboard.py` to write the next version.

## Build

Write `/workspace/dashboard.py`, run it once with `python3 /workspace/dashboard.py`, and print what it loaded. Charts are [Altair](https://altair-viz.github.io/) rendered to static SVG, embedded in one HTML file (no JavaScript, so it opens anywhere):

```python
import pandas as pd, altair as alt, vl_convert as vlc

monthly = pd.read_csv("/workspace/data/monthly_revenue.csv", parse_dates=["month"])
print(f"monthly_revenue: {len(monthly)} rows, {monthly.month.min():%Y-%m} to {monthly.month.max():%Y-%m}")

BILLIONS = alt.Axis(labelExpr="'$' + format(datum.value / 1e9, '.1f') + 'B'")

def svg(chart):
    styled = (chart.configure_view(stroke=None)
              .configure_axis(gridColor="#EEF1F4", domain=False, labelColor="#57606A")
              .configure_title(anchor="start", fontSize=15, fontWeight=600))
    return vlc.vegalite_to_svg(styled.to_json())

actual = alt.Chart(monthly).mark_line(strokeWidth=2, color="#2F6FEB").encode(
    x=alt.X("month:T", title=None),
    y=alt.Y("revenue:Q", title=None, scale=alt.Scale(zero=False), axis=BILLIONS),
)
trend = actual.properties(width=980, height=300, title="Monthly revenue")   # fixed widths: SVG has no container

kpis = [("Total revenue", f"${monthly.revenue.sum() / 1e9:.1f}B"), ("Avg / month", f"${monthly.revenue.mean() / 1e9:.2f}B")]
cards = "".join(f'<div class="card"><div class="label">{label}</div><div class="value">{value}</div></div>' for label, value in kpis)

html = f"""<!doctype html><html><head><meta charset="utf-8"><title>Revenue dashboard</title><style>
body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#F6F8FA;color:#1F2328;margin:0}}
.wrap{{max-width:1100px;margin:0 auto;padding:32px 24px}} h1{{margin:0;font-size:26px}} .sub{{color:#57606A;margin:6px 0 20px}}
.kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:14px}}
.card{{background:#fff;border:1px solid #D8DEE4;border-radius:12px;padding:16px;margin-bottom:14px}}
.label{{color:#57606A;font-size:13px}} .value{{font-size:26px;font-weight:650}}
.grid{{display:grid;grid-template-columns:2fr 1fr;gap:14px}} svg{{max-width:100%;height:auto}}
</style></head><body><div class="wrap">
<h1>Revenue dashboard</h1><div class="sub">Source: Snowflake sales semantic view</div>
<div class="kpis">{cards}</div>
<div class="card">{svg(trend)}</div>
</div></body></html>"""
open("/workspace/out/dashboard_v1.html", "w").write(html)
open("/workspace/out/preview_v1.png", "wb").write(vlc.vegalite_to_png(trend.to_json(), scale=2))
```

Guidelines:
- 4 KPI cards: the headline total, growth vs the prior period, the top contributor, and one that answers the question.
- One full-width trend (`width=980`), then breakdowns in a `.grid` row (`width=580` charts, or a text card on the right).
- Mention caveats (partial periods) in the subtitle or a text card.

## Forecast (follow-up turns)

Make the modeling visible: the script prints each step, and you report them.

```python
from statsmodels.tsa.holtwinters import ExponentialSmoothing

y = monthly.set_index("month")["revenue"].asfreq("MS")
y = y[:-1] if partial_last_month else y              # drop a partial final period first

def fit(series):
    return ExponentialSmoothing(series, trend="add", seasonal="add", seasonal_periods=12).fit()

# 1. Backtest: train on all but the last 6 months, predict them, measure the error.
train, test = y[:-6], y[-6:]
mape = (abs(fit(train).forecast(6).values - test.values) / test.values).mean() * 100
print(f"backtest: trained on {len(train)} months ({train.index[0]:%Y-%m} to {train.index[-1]:%Y-%m}), "
      f"predicted the last 6, MAPE = {mape:.1f}%")

# 2. Train on everything and forecast.
model = fit(y)
p = model.params
print(f"model: Holt-Winters on {len(y)} months, alpha={p['smoothing_level']:.2f} "
      f"beta={p['smoothing_trend']:.2f} gamma={p['smoothing_seasonal']:.2f}")
fc = model.forecast(6)
sigma = (y - model.fittedvalues).std()
forecast = pd.DataFrame({"month": fc.index, "revenue": fc.values,
                         "low": fc.values - 1.96 * sigma, "high": fc.values + 1.96 * sigma})
print("forecast:", ", ".join(f"{m:%b %Y} ${v / 1e9:.2f}B" for m, v in zip(forecast.month, forecast.revenue)))

band = alt.Chart(forecast).mark_area(opacity=0.2, color="#E8743B").encode(x="month:T", y="low:Q", y2="high:Q")
predicted = alt.Chart(forecast).mark_line(strokeDash=[6, 4], strokeWidth=2, color="#E8743B").encode(x="month:T", y="revenue:Q")
trend = (band + actual + predicted).properties(width=980, height=300, title="Monthly revenue, with 6-month forecast (dashed, 95% band)")
```

On the dashboard: add a "6-month forecast" KPI and a "Backtest error" KPI, put the band and dashed line on the trend, and add a "Forecast model" card (method, months trained on, backtest MAPE, how the band is computed). The preview PNG should show the forecast too.

In your answer, add a short **How I built the forecast** section: what data it trained on, the backtest result in plain words ("predicting the last 6 known months, it was off by 0.8% on average"), the method, and its limits.

## Versions and sharing

- Never overwrite a shared file: write the next version (`dashboard_v2.html`, `preview_v2.png`) and keep earlier ones.
- Call `share_file` on the new preview PNG and the new HTML, in parallel. Use the placeholders they return (each names its file).
