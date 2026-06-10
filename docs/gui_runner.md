# GUI Runner Guide

`counter-risk gui` provides a macro-free operator interface for monthly runs.

## Install (packaged operators)

For operator machines that do not have Python/CLI tooling:

1. Build the release bundle from this repo root:

   ```bash
   pyinstaller release.spec
   ```

2. Copy the generated `dist/counter-risk/` folder to the approved shared location.
3. Ensure `config/` and `templates/` are present alongside the executable (the spec bundles them).
4. Operators launch `counter-risk` from that folder and use `counter-risk gui`.

If your environment blocks Tkinter, use `counter-risk gui --headless` (CI/smoke) or
fall back to `Runner.xlsm`.

## Launch

```bash
counter-risk gui
```

The window exposes:

- As-Of Date
- Mode (`all`, `ex_trend`, `trend`)
- Discovery mode (`manual`, `discover`)
- Strict policy (`warn`, `strict`)
- Formatting profile
- Input root
- Output root

Buttons:

- `Run`
- `Dry-Run Discovery`
- `Open Output Folder`
- `Open Manifest`
- `Open Summary`
- `Open PPT Folder` opens the run folder that contains the registered PPT outputs.

Run output folders use the pipeline repeat-run convention: the first run for a
month lands in `<output_root>/<YYYY-MM-DD>`, and same-date repeats advance to
`<YYYY-MM-DD>_1`, `<YYYY-MM-DD>_2`, and so on. The GUI passes the selected
empty run folder to the CLI and keeps the completed folder as the target for the
post-run open buttons.

## Headless Smoke Mode

Use CI/headless mode to validate command wiring without opening a Tk window:

```bash
counter-risk gui --headless --as-of-date 2025-12-31 --mode all
```

For discovery-only smoke runs:

```bash
counter-risk gui --headless --dry-run-discovery --as-of-date 2025-12-31
```

## Settings Serialization

GUI runs write `counter-risk-runner-settings-*.json` under the system temp directory and pass it through `--settings` to the `run` command. The same settings contract as `Runner.xlsm` is used:

- `input_root`
- `discovery_mode`
- `strict_policy`
- `formatting_profile`
- `output_root`
