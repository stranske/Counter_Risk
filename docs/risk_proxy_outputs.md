# Risk Proxy Outputs

Each pipeline run attempts to create deterministic risk-weighted proxy outputs
from parsed totals rows. The outputs are optional because the source workbooks
do not always carry volatility, position, or prior-period delta columns.

## Where the outputs land

- `<run_dir>/risk_rankings.csv` - written when at least one proxy has the
  required current-period input columns.
- `<run_dir>/risk_top_movers.csv` - written when a computed proxy also has a
  prior-period delta column available.
- `<run_dir>/manifest.json` - always includes `risk_proxy_summary`, which tells
  operators which proxies were computed, which were skipped, and why.

## Proxy formulas

| Proxy name | Required columns | Formula |
| --- | --- | --- |
| `risk_proxy_notional_annualized_volatility` | `Notional`, `AnnualizedVolatility` | `Notional * AnnualizedVolatility` |
| `risk_proxy_position_usd_vol` | `PositionUSD`, `Vol` | `PositionUSD * Vol` |

Rankings sort by descending absolute proxy value, then by counterparty name
case-insensitively. This makes tied rows stable across reruns.

## Top movers

`risk_top_movers.csv` is written only when prior-period delta columns are
present:

- Notional proxy: `NotionalChange` or `NotionalChangeFromPriorMonth`
- Position proxy: `PositionUSDChange` or `PositionChangeFromPriorMonth`

Mover rows report current proxy value, inferred prior proxy value, delta,
absolute delta, rank, and the delta source column used. Missing prior-period
delta columns skip only the mover output for that proxy; rankings still write
when current proxy inputs exist.

## Missing data behavior

When required columns are missing, the pipeline records warnings and marks the
proxy as `skipped` under `manifest["risk_proxy_summary"]["by_variant"]`.
Missing volatility or position inputs do not fail the run. Missing mover delta
inputs skip only `risk_top_movers.csv` for the affected proxy.
