# GUI Runner Guide

`counter-risk gui` provides a macro-free operator interface for monthly runs.

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
- `Open PPT Folder`

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

GUI runs write `counter-risk-runner-settings.json` under the system temp directory and pass it through `--settings` to the `run` command. The same settings contract as `Runner.xlsm` is used:

- `input_root`
- `discovery_mode`
- `strict_policy`
- `formatting_profile`
- `output_root`
