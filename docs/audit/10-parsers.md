# Parsers Subsystem Audit

Summary: The parser subsystem is generally well-structured, defensive, and fails loudly on missing sheets/headers/segments rather than silently producing wrong numbers. The main robustness gap is a **UTF-8 BOM bug** that breaks CSV/overrides ingestion exactly on the Windows operator path (Excel "CSV UTF-8" exports). Secondary risks: locale/number-format assumptions (US-only, no European decimal-comma support) and the CPRS-FCM parser's reliance on hard-coded column indices instead of a header map (unlike CPRS-CH). There is substantial, low-risk duplication across the two XML-reading parsers and the four `_coerce_float`/`_extract_numeric` helpers that could be consolidated.

## Summary

Files audited:
- `src/counter_risk/parser.py` (thin row helper)
- `src/counter_risk/parsers/__init__.py`, `_variant_text.py`
- `src/counter_risk/parsers/cprs_ch.py`
- `src/counter_risk/parsers/cprs_fcm.py`
- `src/counter_risk/parsers/daily_holdings_pdf.py`
- `src/counter_risk/parsers/exposure_maturity_schedule.py`
- `src/counter_risk/parsers/nisa.py` (+ `nisa_all_programs.py`, `nisa_trend.py`, `nisa_ex_trend.py` shims)
- `src/counter_risk/parsers/repo_cash_sources.py`

Overall the parsers prefer explicit `ValueError`/typed exceptions over silent zeros, validate numeric ranges (`cprs_ch._validate_numeric_ranges`), and assert non-empty output. That is a strong foundation. The findings below are the concrete gaps.

## Code Quality Findings

### [BLOCKER] UTF-8 BOM breaks CSV ingestion on the Windows operator path
`repo_cash_sources.py:186` opens CSVs with `encoding="utf-8"` (not `utf-8-sig`). Excel's "CSV UTF-8 (Comma delimited)" export — the most likely format a Windows operator produces — prepends a BOM. The BOM attaches to the first header, so `_normalize_header` (`repo_cash_sources.py:263`, which only `.strip().casefold().replace(" ","_")`s) yields `"﻿counterparty"` rather than `"counterparty"`.

Consequences:
- `load_repo_cash_overrides_csv` (`:39`) reports `missing required columns: counterparty` and raises, blocking the override flow.
- `_rows_to_repo_cash_mapping` (`:243`) raises "must include counterparty and cash columns" for a structured CSV source that visually looks correct.

Verified locally: `open(..., encoding="utf-8")` + `csv.DictReader` yields key `'﻿counterparty'`, and `.strip()` does not remove `﻿`. Fix: open with `encoding="utf-8-sig"` (or strip a leading BOM in `_normalize_header`). This is the highest-impact resilience gap because it fires on the normal Windows path, not an edge case.

### [MAJOR] CPRS-FCM uses hard-coded column indices instead of a header map
Unlike `cprs_ch.py` (which builds a `_build_column_map` from header aliases), `cprs_fcm.py` reads totals and futures rows from fixed columns: totals at columns 3/5/6/7/8/9/11/12 (`cprs_fcm.py:143-167`) and futures detail at 3/5/7/8/9/12 (`:198-218`). Any column insertion/removal or layout drift in the MOSERS "CPRS - FCM" sheet silently maps the wrong cells to TIPS/Treasury/Notional etc., producing *wrong numbers with no error*. This is the classic "silent wrong number" failure the audit is meant to surface. Recommend aligning CPRS-FCM with the CPRS-CH header-mapping approach.

### [MAJOR] US-only number/locale assumptions; European decimals silently corrupted
All four numeric coercers (`nisa._coerce_float:190`, `cprs_ch._extract_numeric:405`, `cprs_fcm._extract_numeric:414`, `exposure_maturity._coerce_float:95`, plus `daily_holdings_pdf._parse_amount:225`) unconditionally strip `","` as a thousands separator and treat `"."` as the decimal point. A European-formatted cell like `"1.234,56"` becomes `"1.23456"` — parsed successfully as a *wrong* number, with no error raised. Given the project is MOSERS/US-centric this is likely acceptable today, but it is an undocumented assumption that silently miscomputes rather than failing. Worth at minimum a documented contract; ideally a guard that rejects ambiguous comma-decimal patterns.

### [MINOR] Percent values are de-symbolized but not rescaled
`nisa._coerce_float:202`, `cprs_ch._extract_numeric:417`, and `cprs_fcm._extract_numeric:419` strip `"%"` but do not divide by 100, so `"5%"` becomes `5.0`, not `0.05`. This is internally consistent only if every downstream consumer expects whole-number percents for `AnnualizedVolatility`. If a source ever supplies the same column as a true ratio (`0.05`) or with a `%`, the two will be off by 100x with no detection. Confirm the downstream contract and document it.

### [MINOR] PDF fallback decodes arbitrary bytes as UTF-8 with errors ignored
`daily_holdings_pdf._extract_text:94-95` falls back to `path.read_bytes().decode("utf-8", errors="ignore")` when pdfplumber/pypdf/OCR all fail. For a real (binary) PDF this yields garbage text, then `_extract_repo_cash_values` finds no counterparties and the function raises a clear `DailyHoldingsPdfError` (`:67`) — so it fails loudly, which is good. The risk is narrow: a corrupt/partial PDF whose stray bytes happen to match a counterparty alias + amount regex could yield a partial wrong mapping. Low likelihood; flagging because the silent `errors="ignore"` path is the weakest link in an otherwise loud parser. The comment says this fallback exists for sanitized text-file fixtures — consider gating it to `.txt`-like inputs or logging when it is used.

### [MINOR] `__init__.py` exports `parse_nisa_all_programs` from `nisa`, leaving `nisa_all_programs.py` as a dead alias
`parsers/__init__.py:14` imports `parse_nisa_all_programs` from `counter_risk.parsers.nisa`, while `nisa_all_programs.py` is a pure re-export shim of the same symbols. Harmless but adds an extra hop and a file that exists only for backward-compat. See Duplication section.

### [MINOR] Negative-paren handling depends on prior dash normalization, not obvious at call site
In `daily_holdings_pdf`, lines are run through `canonicalize_name` (which converts en/em-dashes to `-`) before the `_AMOUNT_PATTERN` regex (`:172-176`). The numeric coercers elsewhere rely on the same dash normalization happening upstream in `_normalize_text`. This works but is implicit; a future change to `safe_display_name`/`canonicalize_name` dash handling could silently change numeric parsing. Worth a unit test pinning negative/parenthesized values across all coercers.

## Duplication / Simplification Opportunities

1. **Two near-identical hand-rolled XLSX XML readers.** `cprs_ch.py` and `cprs_fcm.py` each define their own `_XML_NS`, `_load_shared_strings`, `_read_sheet_rows`, `_cell_value`, and `_column_index_from_reference` — byte-for-byte equivalent (compare `cprs_ch.py:465-539` with `cprs_fcm.py:328-401`). These should move to a shared module (e.g. `parsers/_xlsx_xml.py`) alongside the existing `_variant_text.py`. This is the single largest condensation opportunity and reduces the risk of the two copies drifting.

2. **Four copies of the numeric coercer.** `nisa._coerce_float` (`:190`), `cprs_ch._extract_numeric` (`:405`), `cprs_fcm._extract_numeric` (`:414`), and `exposure_maturity._coerce_float` (`:95`) implement the same logic: handle None, sentinel dashes/`N/A`, `(x)` -> `-x`, strip `,$%`, `float()`. They differ only trivially (exposure omits `%`; nisa/exposure accept numeric inputs directly). Consolidate into one shared helper with a flag for currency-only vs percent. `_parse_amount` in `daily_holdings_pdf.py:225` is a fifth variant.

3. **Duplicated variant-detection logic.** `cprs_ch._detect_variant` (`:322`) and `cprs_fcm._variant_for_path` (`:272`) both normalize `"{name} {sheet}"` via `normalize_variant_text` and branch on `"ex trend"`/`"trend"`/`"all"`. They diverge (CPRS-CH also knows `mosers_input`/`all_programs`), but the common scaffold could share a helper, keeping the per-parser segment expectations separate.

4. **`_to_dataframe` duplication.** `cprs_ch._to_dataframe` (`:213`) and `cprs_fcm._to_dataframe` (`:431`) implement the same "build DataFrame, backfill missing columns, reorder, astype" pattern; only the column/dtype tuples differ. `cprs_fcm`'s version is already parameterized by `columns`/`dtypes` — `cprs_ch` could call the same shared helper.

5. **NISA shim trio.** `nisa_all_programs.py`, `nisa_trend.py`, `nisa_ex_trend.py` are all thin re-exports of `nisa.parse_nisa_all_programs` (the trend/ex-trend variants are literal aliases — `nisa_trend.py:14 NisaTrendData = NisaAllProgramsData`, `:17-20` just calls through). If the distinct "trend"/"ex-trend" handling was intended to differ, it currently does not; if not, these can collapse into `nisa.py` once external imports are confirmed migrated.

## Notable Strengths

- **Fails loudly, not silently.** Missing worksheets, missing headers, missing expected segments, empty output, and non-finite/out-of-range numbers all raise typed exceptions (`exposure_maturity_schedule.py:25-34` typed error hierarchy; `cprs_ch._validate_numeric_ranges:189`; `nisa.parse_nisa_all_programs:174-177` empty-output guards). This is the right posture for a financial pipeline.
- **Robust header/sheet discovery.** `cprs_ch._find_header_row` (`:345`), `nisa._select_worksheet_and_headers` (`:219`, scores every sheet and picks the best), and `exposure_maturity._find_header_row_and_map` (`:124`) tolerate header rows not being on row 1 and report the *closest* missing-header set for diagnosis.
- **Format-drift tolerance where it counts.** Header aliasing (`_HEADER_ALIASES`, `_COLUMN_ALIASES`), two-row combined-header handling (`cprs_ch._build_column_map:362`), segment-column inference (`nisa._detect_segment_column:398`), and counterparty alias matching with word-boundary regex (`daily_holdings_pdf._match_counterparty:214`) all handle real-world messiness without guessing numbers.
- **Layered PDF extraction with graceful degradation** (pdfplumber -> pypdf -> OCR), each wrapped in try/except with logging (`daily_holdings_pdf.py:98-165`), and optional dependencies degrade rather than crash.
- **Evidence/provenance tracking** in `cprs_fcm.parse_fcm_totals_with_evidence` (`:91`) records source sheet/row per counterparty — good for auditability of a risk report.
- **Shared `_variant_text.normalize_variant_text` helper** already exists and is used by both CPRS parsers, showing the consolidation pattern the duplication items above should follow.
