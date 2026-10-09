"""Deterministic pseudonyms for DICOM UIDs (no model code; shared by the audit path).

Moved here from training/ground_truth.py (re-exported there) with the SAME salt, so existing
pseudonyms are unchanged.
"""

from __future__ import annotations

import hashlib

PSEUDONYM_SALT = "voxeltrace-pseudonym-v1"


def pseudonym(uid: str | None, prefix: str) -> str:
    if not uid:
        return f"{prefix}_none"
    return f"{prefix}_" + hashlib.sha256(f"{PSEUDONYM_SALT}:{uid}".encode()).hexdigest()[:16]
