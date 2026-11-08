#!/usr/bin/env bash
# Feature 017 T010: pin the model-tier artefacts for a site. Non-GPU: hashing of the models already on disk and one
# small download (the factory machine's cloud image). Every artefact is pinned in recipe.lock.json (FR-017). Re-running resumes and re-verifies.
#
#   deploy/recipe/fetch-artefacts.sh <data-root>      e.g. /mnt/data/forge-c/model-service
set -euo pipefail
ROOT=${1:?data root}
REPO=$(cd "$(dirname "$0")/../.." && pwd)
LOCK=$REPO/deploy/recipe/recipe.lock.json
PY=(uv run --project "$REPO" python -m forge_factory.modelservice.artefacts)
mkdir -p "$ROOT/models" "$ROOT/images"
chmod 0750 "$ROOT"

# The models the owner lane uses today (owner 2026-11-08: "we don't work with qwen 3.6 here"): already on disk as
# content-addressed Ollama blobs, recorded by hash, never re-downloaded. Names are the ones the factory requests.
BLOBS=${OLLAMA_BLOBS:-/mnt/data/forge-c/swe1-fabro-20261031/lrtx/ollama-models/blobs}
"${PY[@]}" file --path "$BLOBS/sha256-de46c4baf4b4dd85ea438bb0f757f21c38841a353506579979bba114311658c3" --lock "$LOCK" \
  --model "hf.co/ornith-ai/Ornith-1.5-35B-A3B-GGUF:Q8_0"
Q38_BLOB=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print([l['digest'] for l in d['layers'] if l['mediaType'].endswith('.image.model')][0].replace(':','-'))" \
  "${OLLAMA_MANIFESTS:-/mnt/data/forge-c/swe1-fabro-20261031/lrtx/ollama-models/manifests}/registry.ollama.ai/library/qwen3.8/27b-q8_0")
"${PY[@]}" file --path "$BLOBS/$Q38_BLOB" --lock "$LOCK" --model "qwen3.8:27b-q8_0"
LLAMA=${LLAMA_SERVER:-/mnt/data/forge-c/swe1-fabro-20261031/lrtx/ollama-0.34.0/lib/ollama/llama-server}
"${PY[@]}" image --name llama-server-ollama-0.34.0 --digest "sha256:$(sha256sum "$LLAMA" | cut -d' ' -f1)" --lock "$LOCK"

# Factory machine base image: the newest dated Ubuntu 22.04 cloud image, checked against its published SHA256SUMS.
REL=$(curl -fsS https://cloud-images.ubuntu.com/releases/jammy/ | grep -o 'release-[0-9]\{8\}' | sort -u | tail -1)
IMG=ubuntu-22.04-server-cloudimg-amd64.img
SUM=$(curl -fsS "https://cloud-images.ubuntu.com/releases/jammy/$REL/SHA256SUMS" | awk -v f="*$IMG" '$2==f{print $1}')
[ -n "$SUM" ] || { echo "no checksum for $IMG in $REL" >&2; exit 4; }
"${PY[@]}" url --url "https://cloud-images.ubuntu.com/releases/jammy/$REL/$IMG" --dest "$ROOT/images/$REL-$IMG" --sha256 "$SUM"
"${PY[@]}" image --name "ubuntu-22.04-cloudimg-$REL" --digest "sha256:$SUM" --lock "$LOCK"
echo "ARTEFACTS_PINNED $LOCK"
