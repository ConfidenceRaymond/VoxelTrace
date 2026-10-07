#!/usr/bin/env bash
# READ-ONLY inventory of VoxelTrace hackathon material. This script deletes NOTHING.
set -uo pipefail
HACK="${VOXELTRACE_HACKATHON_ROOT:-$HOME/voxeltrace_hackathon}"
REPO="$HACK/voxeltrace"

hr() { printf '\n=== %s ===\n' "$1"; }

hr "Hackathon root: $HACK"
if [ -d "$HACK" ]; then
  du -sh "$HACK" 2>/dev/null
  echo
  echo "Top-level sizes:"
  du -sh "$HACK"/* "$HACK"/.[!.]* 2>/dev/null | sort -h
else
  echo "not present"
fi

hr "Contents (depth <= 2, excluding .git and .venv internals)"
[ -d "$HACK" ] && find "$HACK" -maxdepth 2 \
  -not -path '*/.git/*' -not -path '*/.venv/*' | sort

for d in data models outputs logs tmp; do
  hr "$d/ (files, depth <= 3)"
  if [ -d "$HACK/$d" ]; then
    n=$(find "$HACK/$d" -type f | wc -l)
    echo "$n file(s), $(du -sh "$HACK/$d" 2>/dev/null | cut -f1)"
    find "$HACK/$d" -maxdepth 3 | sort | head -50
  else
    echo "absent"
  fi
done

hr "Repository untracked/ignored files (would not be pushed)"
[ -d "$REPO/.git" ] && git -C "$REPO" status --ignored --short | head -50

hr "VoxelTrace / cache environment variables (current shell)"
env | grep -E '^(VOXELTRACE_|PIP_CACHE_DIR|HF_HOME|HF_HUB_CACHE|HUGGINGFACE_HUB_CACHE|TRANSFORMERS_CACHE|VLLM_|TORCH_HOME|XDG_CACHE_HOME)=' \
  | sed -E 's/(API_KEY|TOKEN|SECRET)=.*/\1=<redacted>/' || echo "(none set)"

hr "Redirected caches inside the hackathon tree"
for c in "$HACK/tmp/pip-cache" "$HACK/models/hf-cache" "$HACK/models/vllm-cache"; do
  [ -e "$c" ] && du -sh "$c" || echo "absent: $c"
done

hr "Possible leakage OUTSIDE the hackathon tree (inspect manually)"
for p in "$HOME/.streamlit" "$HOME/.cache/pip" "$HOME/.cache/huggingface" "$HOME/.cache/vllm" "$HOME/.config/gh"; do
  [ -e "$p" ] && echo "present: $p ($(du -sh "$p" 2>/dev/null | cut -f1)) - check whether VoxelTrace created it" \
    || echo "absent:  $p"
done

hr "Docker objects named *voxeltrace*"
if command -v docker >/dev/null 2>&1; then
  if docker info >/dev/null 2>&1; then
    echo "Containers:"; docker ps -a --filter name=voxeltrace --format '  {{.ID}} {{.Names}} {{.Image}} {{.Status}}'
    echo "Images:";     docker images --format '  {{.Repository}}:{{.Tag}} {{.ID}} {{.Size}}' | grep -i voxeltrace || echo "  (none)"
    echo "Volumes:";    docker volume ls --format '  {{.Name}}' | grep -i voxeltrace || echo "  (none)"
  else
    echo "docker daemon not accessible to $(whoami); skipped"
  fi
else
  echo "docker not installed"
fi

printf '\nREAD-ONLY AUDIT: NOTHING DELETED\n'
