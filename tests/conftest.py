"""Keep pytest temporary files inside the hackathon tree (../tmp/pytest), not /tmp."""

from pathlib import Path

HACKATHON_TMP = Path(__file__).resolve().parents[2] / "tmp" / "pytest"


def pytest_configure(config):
    if config.option.basetemp is None:
        HACKATHON_TMP.parent.mkdir(parents=True, exist_ok=True)
        config.option.basetemp = str(HACKATHON_TMP)
