"""Keep pytest temporary files inside the project root (../tmp/pytest), not /tmp."""

from pathlib import Path

PROJECT_TMP = Path(__file__).resolve().parents[2] / "tmp" / "pytest"


def pytest_configure(config):
    if config.option.basetemp is None:
        PROJECT_TMP.parent.mkdir(parents=True, exist_ok=True)
        config.option.basetemp = str(PROJECT_TMP)
