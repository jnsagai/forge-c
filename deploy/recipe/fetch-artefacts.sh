#!/usr/bin/env bash
# Feature 017 T010: fetch and pin the model-tier artefacts for a site. Non-GPU: downloads, `docker pull` and hashing
# only. Every artefact is pinned in recipe.lock.json (FR-017). Re-running resumes and re-verifies.
#
#   deploy/recipe/fetch-artefacts.sh <data-root>      e.g. /mnt/data/forge-c/model-service
set -euo pipefail
ROOT=${1:?data root}
REPO=$(cd "$(dirname "$0")/../.." && pwd)
LOCK=$REPO/deploy/recipe/recipe.lock.json
PY=(uv run --project "$REPO" python -m forge_factory.modelservice.artefacts)
mkdir -p "$ROOT/models" "$ROOT/images"
chmod 0750 "$ROOT"

# Production reference model on this site: official FP8 checkpoint at an exact commit (research R2).
QWEN_REPO=Qwen/Qwen3.6-35B-A3B-FP8
QWEN_REV=c653bba46dfa06e9658dcc0b0dc87fe4685f14a2
"${PY[@]}" hf --repo "$QWEN_REPO" --revision "$QWEN_REV" --dest "$ROOT/models/qwen3.6-35b-a3b-fp8" \
  --lock "$LOCK" --model qwen3.6-35b-a3b-fp8

# Inference engine: vLLM release pinned by digest (research R1); verified to know the model architecture.
VLLM=vllm/vllm-openai@sha256:befccf0e7e4089aa23926bb6f887a85c0d46c2a99e6de5c5ffdf5cb7957c5b34   # v0.32.0
docker pull -q "$VLLM"
docker run --rm --network none --entrypoint python3 "$VLLM" -c \
  "from vllm.model_executor.models.registry import ModelRegistry as R; import vllm, sys; \
a='Qwen3_5MoeForConditionalGeneration'; print('vllm', vllm.__version__, a, a in R.get_supported_archs()); \
sys.exit(0 if a in R.get_supported_archs() else 3)"
"${PY[@]}" image --name vllm-openai --digest "${VLLM#*@}" --lock "$LOCK"

# Today's Ornith model (owner lane): already on disk, recorded by hash, never re-downloaded.
ORNITH=${ORNITH_BLOB:-/mnt/data/forge-c/swe1-fabro-20261031/lrtx/ollama-models/blobs/sha256-de46c4baf4b4dd85ea438bb0f757f21c38841a353506579979bba114311658c3}
"${PY[@]}" file --path "$ORNITH" --lock "$LOCK" --model ornith-1.5-35b-a3b-q8
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
