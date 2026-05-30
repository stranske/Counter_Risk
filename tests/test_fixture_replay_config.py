from pathlib import Path

import yaml


def test_fixture_replay_config_paths_exist() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    config_path = repo_root / "config" / "fixture_replay.yml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config_dir = config_path.parent

    required_paths = [
        "mosers_all_programs_xlsx",
        "mosers_ex_trend_xlsx",
        "mosers_trend_xlsx",
        "hist_all_programs_3yr_xlsx",
        "hist_ex_llc_3yr_xlsx",
        "hist_llc_3yr_xlsx",
        "monthly_pptx",
    ]

    missing = []
    for key in required_paths:
        candidate = Path(config[key])
        if not candidate.is_absolute():
            candidate = (config_dir / candidate).resolve()
        if not candidate.exists():
            missing.append(f"{key}: {candidate}")

    assert not missing, "fixture_replay.yml includes non-existent input paths:\n" + "\n".join(
        missing
    )
