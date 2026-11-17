#!/usr/bin/env bash
# Copyright The Phorepoc Authors
# SPDX-License-Identifier: Apache-2.0

# recipes/jars.sh -- TEMPORARY until P2 (the VM's CLDC library): JRT's classes as jars, one per DLL
# (recipes/build_jars.py), into $PHOREPOC_BUILD/jrt/jars. Needs a JDK (javac, jar); prepare.sh runs it in a JDK image.
set -eu
: "${PHOREPOC_BUILD:?}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
python3 "$HERE/recipes/build_jars.py" --jrt "$PHOREPOC_BUILD/jrt/oss.FCL.sf.app.JRT" --out "$PHOREPOC_BUILD/jrt/jars"
