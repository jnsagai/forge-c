#!/usr/bin/env bash
# Owner decision 2026-11-03 (SWE.4 requirement-based unit tests in GoogleTest/GoogleMock): build the pinned
# GoogleTest/GoogleMock 1.11.0 from the distribution source tree (/usr/src/googletest, Debian package googletest
# 1.11.0-3) with the factory's pinned LLVM 19 clang++ into a NEW toolchain directory. Never overwrites an existing
# installation (refuses), never touches other toolchain directories. Licence: BSD-3-Clause (Google Inc.).
#
# usage: scripts/build_googletest.sh <toolchains dir> [<llvm bin dir>]
# result: <toolchains dir>/googletest-1.11.0/{include,lib,forge-toolchain.json}
set -euo pipefail
TC="${1:?toolchains dir}"
LLVM_BIN="${2:-$TC/LLVM-19.1.7-Linux-X64/bin}"
SRC=/usr/src/googletest
VERSION=1.11.0
DEST="$TC/googletest-$VERSION"
[ -e "$DEST" ] && { echo "REFUSED: $DEST exists (build into a new directory only)" >&2; exit 2; }
[ -x "$LLVM_BIN/clang++" ] || { echo "REFUSED: no clang++ in $LLVM_BIN" >&2; exit 2; }
grep -q "GOOGLETEST_VERSION $VERSION" "$SRC/CMakeLists.txt" || { echo "REFUSED: $SRC is not googletest $VERSION" >&2; exit 2; }
[ -f "$SRC/googlemock/src/gmock-all.cc" ] || { echo "REFUSED: $SRC has no googlemock source" >&2; exit 2; }
# source identity: sha256 over the sorted (path, sha256) list of every source file (host-independent)
SRC_SHA=$(cd "$SRC" && find . -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum | sha256sum | cut -d' ' -f1)
# a host whose newest GCC has no libstdc++ (Omniverse2: gcc 12 without libstdc++-12-dev) names the GCC installation
# clang++ links against; the flag is recorded and reused for every gtest build (forge_factory.gtest_toolchain)
CXX_FLAGS=""
[ -n "${GCC_INSTALL_DIR:-}" ] && CXX_FLAGS="--gcc-install-dir=$GCC_INSTALL_DIR"
WORK=$(mktemp -d "${TMPDIR:-/tmp}/googletest-build.XXXXXX")
trap 'rm -rf "$WORK"' EXIT
cmake -S "$SRC" -B "$WORK/b" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER="$LLVM_BIN/clang++" \
  -DCMAKE_C_COMPILER="$LLVM_BIN/clang" -DCMAKE_CXX_FLAGS="$CXX_FLAGS" -DCMAKE_EXE_LINKER_FLAGS="$CXX_FLAGS" -DCMAKE_INSTALL_PREFIX="$WORK/i" -DBUILD_GMOCK=ON -DINSTALL_GTEST=ON \
  -DCMAKE_POSITION_INDEPENDENT_CODE=ON -Dgtest_disable_pthreads=OFF >/dev/null
cmake --build "$WORK/b" -j "${JOBS:-4}" >/dev/null
cmake --install "$WORK/b" >/dev/null
mkdir -p "$DEST"
cp -a "$WORK/i/include" "$DEST/include"
mkdir -p "$DEST/lib"
cp -a "$WORK/i"/lib*/libg*.a "$DEST/lib/"
cp "$SRC/googletest/../googletest/README.md" "$DEST/README.googletest.md" 2>/dev/null || true
[ -f /usr/share/doc/googletest/copyright ] && cp /usr/share/doc/googletest/copyright "$DEST/LICENSE.debian-copyright"
LIBS=$(cd "$DEST/lib" && sha256sum libgtest.a libgtest_main.a libgmock.a libgmock_main.a | \
       awk '{printf "%s\"%s\": \"%s\"", (NR>1?", ":""), $2, $1}')
CXX_VER=$("$LLVM_BIN/clang++" --version | head -1)
FLAGS_JSON=$([ -n "$CXX_FLAGS" ] && printf '"%s"' "$CXX_FLAGS" || true)
cat > "$DEST/forge-toolchain.json" <<EOF
{"schema": "forge-c/toolchain/1", "name": "GoogleTest/GoogleMock", "version": "$VERSION",
 "license": "BSD-3-Clause", "source": "$SRC (Debian googletest 1.11.0-3)", "source_tree_sha256": "$SRC_SHA",
 "compiler": "$CXX_VER", "cxx_flags": [$FLAGS_JSON], "libraries_sha256": {$LIBS}}
EOF
chmod -R a-w "$DEST"
echo "$DEST"
cat "$DEST/forge-toolchain.json"
