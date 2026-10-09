# Resume VoxelTrace on a new Linux PC

Written 2026-10-09 when leaving the NVIDIA GB10 (aarch64, Ubuntu 24.04, Python 3.12.3). **Do
not assume the new machine is ARM64.** Everything below works on x86_64 too.

> **Never reuse the GB10 `.venv`** (or any `tmp/*-venv`). Those environments contain aarch64
> binaries and absolute interpreter paths. They are excluded from the copy on purpose. Always
> create a fresh environment.

## Layout to restore

```
<workspace>/                 e.g. /home/<you>/voxeltrace_hackathon
  voxeltrace/                git repository (with .git)
  data/                      downloaded public DICOM + provenance manifests + census
  models/                    Qwen3-VL-8B-Instruct (revision 0c351dd) + manifest
  outputs/                   audits, bundles, reviews, frozen evaluation outputs
  logs/                      progress log, reports (logs/claude_last_report.txt)
  tmp/                       small analysis notes only (venvs and caches excluded)
  MIGRATION_MANIFEST_20261009.txt  MIGRATION_EXCLUDES_20261009.txt  MIGRATION_SHA256_20261009.txt
```

`data/`, `models/`, `outputs/`, `logs/` and `tmp/` must stay **siblings** of the repository.
`configs/default.yaml` resolves them as `../data`, `../models` and so on.

## 1. Copy (or clone) the source

**Preferred: copy the whole workspace from the SSD.**

- **ext4 SSD:** use rsync. It preserves symlinks and hard links.

  ```bash
  rsync -aH --info=progress2 /media/<ssd>/voxeltrace_hackathon/ ~/voxeltrace_hackathon/
  ```

- **exFAT/NTFS SSD:** it cannot store symlinks, so the copy must travel as a tar archive.

  ```bash
  tar -C /home/dell -cf /media/<ssd>/voxeltrace_hackathon_20261009.tar \
      --exclude-from=voxeltrace_hackathon/MIGRATION_EXCLUDES_20261009.txt voxeltrace_hackathon
  tar -C ~ -xf /media/<ssd>/voxeltrace_hackathon_20261009.tar
  ```

**Code-only alternative:**

```bash
git clone https://github.com/ConfidenceRaymond/VoxelTrace.git voxeltrace
```

Data, models and outputs still come from the SSD.

Check the code state:

```bash
cd ~/voxeltrace_hackathon/voxeltrace
git status
git log -1 --oneline   # expect 200b1ff or later
git fetch origin && git rev-parse 'v0.3.0-external-validation^{commit}'   # expect a46526c...
```

### Absolute symlinks: required if the workspace path is not `/home/dell/voxeltrace_hackathon`

`outputs/` holds 13,788 symlinks to files in `data/`. They are **absolute**
(`/home/dell/voxeltrace_hackathon/...`). If the new path differs, rewrite them once:

```bash
OLD=/home/dell/voxeltrace_hackathon
NEW=$HOME/voxeltrace_hackathon
find "$NEW" -path "$NEW/voxeltrace/.venv" -prune -o -type l -lname "$OLD/*" -print0 |
  while IFS= read -r -d '' l; do t=$(readlink "$l"); ln -sfn "$NEW${t#"$OLD"}" "$l"; done
find "$NEW" -xtype l | wc -l    # expect 0 broken links
```

No YAML configuration contains the old absolute path. `scripts/check_environment.sh` (a
development helper) does, so edit it if you use it.

## 2. Recreate the Python environment (Python ≥ 3.11; 3.12 was used)

```bash
cd ~/voxeltrace_hackathon/voxeltrace
python3 -m venv .venv
. .venv/bin/activate
export PIP_CACHE_DIR=~/voxeltrace_hackathon/tmp/pip-cache   # keep caches inside the workspace
pip install -U pip
```

## 3. Install the package

```bash
pip install -e ".[app,dev]"
voxeltrace --version          # expect 0.3.0 and rule bundle 413186131a35...
```

The versions used on the GB10 are recorded in `MIGRATION_MANIFEST_20261009.txt`. Pin them if
a result must be reproduced exactly.

## 4. Configure data, model and output roots

- **Default:** nothing to do. The roots are `../data`, `../models`, `../outputs`, `../logs` and
  `../tmp`, relative to the repository.
- **Override any root** with an environment variable: `VOXELTRACE_DATA_DIR`,
  `VOXELTRACE_MODELS_DIR`, `VOXELTRACE_OUTPUTS_DIR`, `VOXELTRACE_LOGS_DIR`,
  `VOXELTRACE_TMP_DIR`.
- **Product-workflow defaults** (app pages, `data-inventory`) use `VOXELTRACE_WORKSPACE`,
  otherwise the parent of the source checkout.
- **Hugging Face cache:** `export HF_HOME=~/voxeltrace_hackathon/models/hf-cache`, only if a
  model is ever loaded.

## 5. Run the tests

```bash
python -m pytest -q        # expect 637 passed (as on 2026-10-09)
ruff check . && ruff format --check . && git diff --check
```

Check exit codes directly. Do not pipe test output through other commands.

## 6. Verify data and evidence bundles

From the workspace root:

```bash
cd ~/voxeltrace_hackathon
sha256sum -c --quiet MIGRATION_SHA256_20261009.txt && echo ALL_OK   # data, outputs, logs, model metadata
for b in outputs/external_validation_cohort_v1/audit/audit_bundle \
         outputs/commercial_demo_audit/audit/audit_bundle \
         outputs/pilot_runs/e2e_168/audit_bundle; do voxeltrace verify-bundle "$b"; done
```

`MIGRATION_SHA256` uses workspace-relative paths, so `sha256sum -c` must run from the
workspace root. Symlinks are not listed; their targets in `data/` are.

## 7. Verify the model files

`models/Qwen3-VL-8B-Instruct.manifest.json` records the repository (`Qwen/Qwen3-VL-8B-Instruct`),
the revision (`0c351dd01ed87e9c1b53cbc748cba10e6187ff3b`) and the SHA256 of the four
safetensors shards. Check the shards against it (takes about a minute):

```bash
cd ~/voxeltrace_hackathon/models
python3 - <<'EOF'
import hashlib, json
m = json.load(open("Qwen3-VL-8B-Instruct.manifest.json"))
bad = 0
for f in m["files"]:
    if f["sha256"]:
        h = hashlib.sha256()
        with open(f"Qwen3-VL-8B-Instruct/{f['file']}", "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 24), b""):
                h.update(chunk)
        ok = h.hexdigest() == f["sha256"]
        bad += not ok
        print(f["file"], "OK" if ok else "MISMATCH")
print("ALL_OK" if not bad else f"{bad} MISMATCH")
EOF
```

The model is optional. **No audit uses it.**

## 8. Launch the app

```bash
cd ~/voxeltrace_hackathon/voxeltrace
. .venv/bin/activate
streamlit run app/Home.py --server.address 127.0.0.1
```

Or run `scripts/run_app.sh`.

## 9. Resume the work

1. Read `~/voxeltrace_hackathon/logs/claude_last_report.txt` (final migration report) and
   `docs/migration_checkpoint_20261009.md`.
2. Read `docs/autonomous_work_ledger.md` and `docs/commercialization/commercialization_readiness.md`.
3. The progress log is `logs/claude_progress.txt`.
4. Exact next action: see "Next recommended action" in `docs/migration_checkpoint_20261009.md`.
