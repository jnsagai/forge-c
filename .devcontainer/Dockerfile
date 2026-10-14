# Forge-C v0.4 reproducible Ubuntu development container (OSS only).
FROM ubuntu:22.04
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git cmake ninja-build gcc g++ cppcheck clang-tidy gcovr graphviz \
      gcc-arm-none-eabi binutils-arm-none-eabi xz-utils python3 python3-venv \
    && rm -rf /var/lib/apt/lists/*
# Pinned LLVM 19.1.7 (MC/DC coverage); verify attestation digest out-of-band per ADR-0001.
ARG LLVM_URL=https://github.com/llvm/llvm-project/releases/download/llvmorg-19.1.7/LLVM-19.1.7-Linux-X64.tar.xz
RUN curl -fsSL "$LLVM_URL" | tar -xJ -C /opt && ln -s /opt/LLVM-19.1.7-Linux-X64 /opt/llvm
ENV PATH=/opt/llvm/bin:$PATH
RUN curl -LsSf https://astral.sh/uv/0.12.17/install.sh | sh
ENV PATH=/root/.local/bin:$PATH
WORKDIR /workspace
