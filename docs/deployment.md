# Deployment (local workstation)

**Supported:** Python 3.11 and 3.12.
- 3.12.3 is verified locally with a fresh virtualenv.
- 3.11 and 3.12 run in CI (`.github/workflows/ci.yml`).
- Linux is tested. Other OSes are untested.

```bash
git clone https://github.com/ConfidenceRaymond/VoxelTrace.git voxeltrace
cd voxeltrace
python3 -m venv .venv && . .venv/bin/activate
pip install -e .              # core: numpy, pydantic, pydicom, nibabel, SimpleITK, PyYAML, Pillow, httpx
pip install -e ".[app]"       # optional: Streamlit review UI
pip install -e ".[dev]"       # optional: pytest, ruff
voxeltrace --help
pytest -q                     # synthetic tests only; no medical data needed
```

**Resources:**
- RAM: about 1.1 GB for 1 subject, about 2.4 GB for 8 subjects.
- CPU: one core per audit process.
- No GPU.
- Disk: input plus small bundles (about 0.5 MB per subject without QC images).

**Network:** not needed for preflight, audit or verification. The census and fetch scripts are
separate developer tools that read public IDC buckets.

**AI components:** none in the audit path. The optional local VLM explanation features are
not installed by default and are never authoritative ([ai_policy.md](ai_policy.md)).
