# Forge-C factory machine, CONTAINER STAND-IN (feature 017, User Story 5, T059; research R9).
# Used on Omniverse2 until the omniverse2 user is in group kvm; then vm/run-vm.sh boots the real VM from the same
# provision.sh. The stand-in does not prove: a separate kernel, a VM network stack, VM memory limits, booting from the
# production image (the isolation report lists these as standin_limitations).
#
# Build context is deploy/recipe (compose.yaml does this):
#   docker build -f factory-machine/container/Dockerfile --build-arg BASE_DIGEST=sha256:<64 hex> ... deploy/recipe
# BASE_DIGEST is REQUIRED: the ubuntu:22.04 index digest recorded in recipe.lock.json "images". No digest, no build.
# Pins (FORGE_PIN_*_SHA256, FORGE_REPO_URL, FORGE_REVISION) come from recipe.lock.json or build args; provision.sh
# refuses before any change when one is missing. No GPU: no NVIDIA/CUDA base, packages or runtime hooks.
ARG BASE_DIGEST
FROM ubuntu:22.04@${BASE_DIGEST}

ARG BASE_DIGEST
RUN case "${BASE_DIGEST}" in \
      sha256:0000000000000000000000000000000000000000000000000000000000000000) echo "BASE_DIGEST is the zero placeholder" >&2; exit 1 ;; \
      sha256:*) d="${BASE_DIGEST#sha256:}"; [ "${#d}" -eq 64 ] && [ -z "$(printf '%s' "$d" | tr -d '0-9a-f')" ] || { echo "BASE_DIGEST malformed" >&2; exit 1; } ;; \
      *) echo "BASE_DIGEST unset or malformed: pass --build-arg BASE_DIGEST=sha256:<64 hex>" >&2; exit 1 ;; \
    esac

# Optional build-time pins (otherwise taken from recipe.lock.json). Checksums and URLs only; never credentials.
ARG FORGE_SITE=omniverse2
ARG FORGE_UID=1000
ARG FORGE_REPO_URL=
ARG FORGE_REVISION=
ARG FORGE_PIN_UV_URL=
ARG FORGE_PIN_UV_SHA256=
ARG FORGE_PIN_LLVM_URL=
ARG FORGE_PIN_LLVM_SHA256=
ARG FORGE_PIN_GNU_ARM_URL=
ARG FORGE_PIN_GNU_ARM_SHA256=
ARG FORGE_PIN_FABRO_URL=
ARG FORGE_PIN_FABRO_SHA256=

COPY recipe.lock.json /opt/forge-c/recipe/recipe.lock.json
COPY factory-machine/provision.sh /opt/forge-c/recipe/factory-machine/provision.sh

RUN chmod 0755 /opt/forge-c/recipe/factory-machine/provision.sh \
 && /opt/forge-c/recipe/factory-machine/provision.sh --container \
 && rm -rf /var/lib/apt/lists/* /var/cache/forge-c/downloads

ENV PATH=/opt/forge-c/bin:/opt/forge-c/toolchains/llvm-19.1.7/bin:/opt/forge-c/toolchains/gcc-arm-none-eabi-10.3-2021.07/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    FORGE_FABRO_BIN=/opt/forge-c/fabro-0.362.0/fabro-x86_64-unknown-linux-musl/fabro \
    FABRO_NO_UPGRADE_CHECK=1 \
    FORGE_DATA_DIR=/srv/forge-c

USER forge
WORKDIR /opt/forge-c/forge-c
