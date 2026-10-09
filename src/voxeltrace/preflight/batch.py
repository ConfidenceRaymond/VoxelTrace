"""Batch preflight of a trial folder.

Layouts recognised (first match wins):
  <root>/<subject>/<timepoint>/...   (trial layout; a directory with sub-directories that
                                      themselves contain DICOM)
  <root>/<subject>/...               (one scan per subject)
  <root>/...                         (a single scan / series directory)
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from voxeltrace.preflight.schema import BatchPreflight
from voxeltrace.preflight.subject import preflight_scan_dir


def _has_files(d: Path) -> bool:
    return any(p.is_file() for p in d.rglob("*"))


def scan_dirs(root: Path) -> list[tuple[str | None, str, Path]]:
    subdirs = sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith("."))
    if not subdirs:
        return [(None, root.name, root)]
    out = []
    for s in subdirs:
        tps = sorted(p for p in s.iterdir() if p.is_dir() and _has_files(p))
        direct = any(p.is_file() for p in s.iterdir())
        if tps and not direct and all(not (t / "trial.yaml").exists() for t in tps):
            # subject/timepoint layout only if the sub-directories look like scans, i.e. not
            # modality folders of a single scan (PET/CT/SEG)
            if {t.name.upper() for t in tps} <= {"PET", "CT", "SEG", "PT", "RTSTRUCT"}:
                out.append((None, s.name, s))
            else:
                out += [(s.name, t.name, t) for t in tps]
        elif _has_files(s):
            out.append((None, s.name, s))
    if not out and _has_files(root):
        return [(None, root.name, root)]
    return out


def preflight_batch(root: str | Path) -> BatchPreflight:
    root = Path(root)
    scans = [preflight_scan_dir(d, subject=subj, scan=scan) for subj, scan, d in scan_dirs(root)]
    series = [s for sc in scans for s in sc.series]
    codes = Counter(
        f.reason_code
        for sc in scans
        for f in sc.findings + [x for s in sc.series for x in s.findings]
    )
    return BatchPreflight(
        root_label=root.name,
        scans=scans,
        summary={
            "scans": len(scans),
            "pet_series": len(series),
            "scan_states": dict(Counter(sc.state for sc in scans)),
            "series_states": dict(Counter(s.state for s in series)),
            "reason_codes": dict(codes.most_common()),
        },
    )
