# Audit 21: Repo-Wide Duplication (src/counter_risk/)

Summary: The single largest, highest-payoff duplication is a hand-rolled raw-XLSX
reader (zip + XML + shared-strings) copied near-byte-identically between the two
CPRS parsers. A second meaningful cluster is the "parse a messy accounting string
to float" helper, which exists in ~4 slightly-drifting copies across parsers — a
correctness risk because the variants disagree on `%` stripping, paren-negatives,
and range validation. Most other modules (outputs/, ppt/, historical_update
layering, config loaders) are appropriately factored and should be left alone.

## Summary

Findings ranked by payoff (lines saved x correctness-risk reduction) vs refactor risk:

| # | Area | Severity | Est. lines saved | Refactor risk |
|---|------|----------|------------------|---------------|
| 1 | Raw-XLSX reader duplicated in cprs_ch.py + cprs_fcm.py | MAJOR | ~110 | Low |
| 2 | Accounting-string-to-float helper (4 drifting copies) | MAJOR | ~40 + drift fix | Low/Med |
| 3 | `_normalize_text` / `_matching_key` parser pair (4 copies) | MINOR | ~20 | Low |
| 4 | openpyxl "validate path + guarded import + open" preamble | MINOR | ~30 | Low |
| 5 | date coercion (`_coerce_date` vs `_coerce_px_date`) | MINOR | ~10 | Med |

The NISA "variants" called out in the brief (`nisa_trend`, `nisa_ex_trend`,
`nisa_all_programs`) are NOT duplication — they are already thin
backward-compatible re-export shims over `parsers/nisa.py` (see Leave-As-Is).

## High-Payoff Consolidations

### 1. Hand-rolled raw-XLSX reader duplicated across both CPRS parsers [MAJOR]

`parsers/cprs_ch.py` and `parsers/cprs_fcm.py` each carry a private, manual
OOXML reader (open the zip, parse `xl/workbook.xml` + rels, resolve the sheet
target, load shared strings, walk `sheetData`, decode cell values, convert A1
column letters to indices). The low-level helpers are effectively identical:

- `_XML_NS` namespace dict — `cprs_ch.py:18-22` vs `cprs_fcm.py:23-27` (identical)
- `_load_shared_strings` — `cprs_ch.py:465-476` vs `cprs_fcm.py:328-339` (identical)
- `_read_sheet_rows` — `cprs_ch.py:479-502` vs `cprs_fcm.py:342-365` (identical)
- `_cell_value` — `cprs_ch.py:505-527` vs `cprs_fcm.py:379-401` (identical)
- `_column_index_from_reference` — `cprs_ch.py:530-539` vs `cprs_fcm.py:368-376` (identical)

The only legitimately different parts are sheet *selection* (`cprs_ch` takes the
first sheet at `_read_first_sheet` 430-462; `cprs_fcm` searches for an FCM sheet
alias at `_read_fcm_sheet` 281-325). Everything below sheet selection is copy-paste.

Recommendation: extract a `parsers/_xlsx_reader.py` (or extend `_variant_text.py`'s
role into a shared `_parsers_common.py`) exposing `read_sheet_rows(sheet_xml,
shared_strings)`, `load_shared_strings(zip)`, `cell_value(...)`,
`column_index_from_reference(...)`, plus a `resolve_sheet_target(zip, selector)`
that takes a predicate so each parser keeps its own sheet-selection rule. This
removes ~110 lines and eliminates the risk of the two readers drifting (e.g. a
fix to boolean/inlineStr handling currently has to be applied twice). Refactor
risk is low: pure, well-covered functions with no external state.

### 2. "Accounting string to float" helper exists in ~4 drifting copies [MAJOR]

The logic to turn `"$1,234"`, `"(500)"`, `"-"`, `"N/A"` etc. into a float is
re-implemented several times with subtle, behavior-changing differences:

- `parsers/cprs_ch.py:405-427` `_extract_numeric` — strips `, $ %`; treats
  `{"", "-", "--", "N/A", "n/a"}` as 0.0; paren-negatives; has a column-index
  `None` guard.
- `parsers/cprs_fcm.py:414-428` `_extract_numeric` — same body **minus** the
  column-index guard (different signature).
- `parsers/nisa.py:190-206` `_coerce_float` — strips `, $ %`; paren-negatives;
  passes through `int/float`; uses `safe_display_name`-based `_normalize_text`.
- `parsers/exposure_maturity_schedule.py:95-111` `_coerce_float` — same as nisa
  **except it does NOT strip `%`** and uses a `canonicalize_name`-based
  `_normalize_text`.
- `chat/session.py:673-705` `_extract_numeric_value` — yet another variant
  (`strip().replace(",", "")`, returns `None` on failure).

The divergence is the real problem, not just the line count: `%` is stripped in
three copies but silently not in `exposure_maturity_schedule`, and only
`cprs_ch` applies an out-of-range guard (`abs(value) > 1e15`,
`_validate_numeric_ranges` 189-210). A value that parses in one parser can
behave differently in another.

Recommendation: add a single `parsers/_numeric.py` (or put it in `normalize.py`)
`coerce_accounting_float(value, *, strip_percent=True) -> float` and have all
parser copies delegate. Pick the intended `%` behavior deliberately rather than
inheriting whatever each copy happened to do. Low refactor risk for the four
parser copies; treat `chat/session.py` separately (it returns `None`, not 0.0).

## Medium / Low Payoff

### 3. `_normalize_text` / `_matching_key` parser pair duplicated [MINOR]

The `_normalize_text` + `_matching_key` pair (`canonicalize_name(normalize).casefold()`)
appears in `parsers/cprs_ch.py:233-240`, `parsers/cprs_fcm.py:404-411`,
`parsers/nisa.py:182-187`, and a `_normalize_text` in
`parsers/exposure_maturity_schedule.py:91-92`. The cprs/nisa pairs are identical
in intent though the underlying `_normalize_text` differs (`safe_display_name`
with `\n`->space in cprs; `safe_display_name(str(value or ""))` in nisa;
`canonicalize_name(str(...))` in exposure). Fold into the same shared parser
module created for items 1-2. Low payoff alone but free if done with #1/#2.

### 4. openpyxl load preamble repeated across xlsx parsers [MINOR]

Several parsers repeat: check `path.exists()` -> check `.xlsx` suffix ->
`try: from openpyxl import load_workbook except ModuleNotFoundError: raise
RuntimeError(...)` -> `load_workbook(... read_only=True, data_only=True)` wrapped
in a broad `except` re-raising a domain error. See `parsers/nisa.py:138-149`,
`parsers/exposure_maturity_schedule.py:50-73`, and
`parsers/repo_cash_sources.py:204-210`. The error-type handling diverges
(`nisa` catches bare `Exception`; `exposure_maturity_schedule` builds an
`InvalidFileException`-aware tuple). A shared
`open_xlsx_readonly(path, *, error_label) -> Workbook` would normalize this. Low
payoff, low risk; mainly a consistency win for the broad-`except` in nisa.py:148.

### 5. Date coercion: `_coerce_date` vs `_coerce_px_date` overlap [MINOR]

`dates.py:158-182` `_coerce_date` and `calculations/wal.py:46-56`
`_coerce_px_date` both implement datetime->date / date passthrough / ISO-string
parsing. They differ deliberately: `_coerce_date` returns `None` and also tries
`%m/%d/%Y` / `%m/%d/%y`; `_coerce_px_date` raises and is ISO-only. A shared
`coerce_to_date(value, *, strict)` could back both, but the differing
error/format semantics make this medium refactor risk for modest payoff. Worth
noting; not urgent.

## Leave-As-Is (acceptable duplication)

- `parsers/nisa_trend.py`, `parsers/nisa_ex_trend.py`,
  `parsers/nisa_all_programs.py` — these are already 21-28 line backward-compat
  re-export shims that delegate to `parsers/nisa.py:parse_nisa_all_programs`
  (see nisa_trend.py:17-20, nisa_ex_trend.py:17-20). They are intentional API
  aliases, not duplicated logic. Do not merge.
- `parsers/_variant_text.py:normalize_variant_text` — already the shared helper
  both CPRS parsers call; correct factoring.
- `outputs/` generators (`base.py` Protocol + `registry.py` + per-output
  `generate()` methods in `pdf_export.py`, `ppt_screenshot.py`,
  `historical_workbook.py`, `ppt_link_refresh.py`) — uniform shape by design via
  a shared `OutputGenerator` Protocol; this is a pattern, not duplication.
- `workflows/historical_update.py` and `outputs/historical_workbook.py` both
  import from `writers/historical_update.py` (`append_wal_row`,
  `locate_ex_llc_3_year_workbook`) — proper layering, not copy-paste.
- `ppt/` modules (`concentration_table.py`, `pptx_static.py`,
  `writers/pptx_screenshots.py`) — each does a distinct python-pptx task (build
  table vs insert static image vs in-place picture replacement); shared surface
  is just the python-pptx API, not duplicated logic.
- Config loaders (`config.py:load_config`, `limits_config.py:load_limits_config`,
  plus name_registry/demo_artifact/web_demo) — each loads a different schema with
  different validation (e.g. `limits_config` uses a no-duplicate-key loader).
  Not meaningfully consolidatable.
