#!/usr/bin/env bash
# Copyright The Phorepoc Authors
# SPDX-License-Identifier: Apache-2.0

# recipes/generate.sh -- after fetch.sh, in the toolchain container: what JRT's qmake + sbs build did before compiling.
#   1. the header exports into the tree and $PHOREPOC_BUILD/jrt/epoc32/include (jrt_exports.py)
#   2. an .mmp next to each component's .pro, with its JNI table and javah headers (jrt_pro2mmp.py)
set -eu
: "${PHOREPOC_BUILD:?}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$PHOREPOC_BUILD/jrt"
python3 "$HERE/recipes/jrt_exports.py" --jrt "$OUT/oss.FCL.sf.app.JRT" --out "$OUT/epoc32"
python3 "$HERE/recipes/jrt_pro2mmp.py" --jrt "$OUT/oss.FCL.sf.app.JRT" --sysinc "$OUT/epoc32/include" --platform-hrh "$PHOREPOC_BUILD/epoc32/include/bldcodeline.hrh"
