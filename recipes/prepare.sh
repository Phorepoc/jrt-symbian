#!/usr/bin/env bash
# Copyright The Phorepoc Authors
# SPDX-License-Identifier: Apache-2.0

# recipes/prepare.sh -- run by the build before the components (pdk docs/layering.md), on the host: the JRT tree and
# jni.h at their pins (fetch.sh), then the exports and the generated mmps (generate.sh), in the toolchain container.
# Inside a container already (/.dockerenv), both run directly.
set -eu
: "${PHOREPOC_BUILD:?}" "${PHOREPOC_PDK:?}" "${PHOREPOC_ARCH:?}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"; ROOT="$(dirname "$HERE")"   # (the folder of all the checkouts)
if [ -f /.dockerenv ]; then
	bash "$HERE/recipes/fetch.sh"; bash "$HERE/recipes/generate.sh"
	exit 0
fi
docker run --rm -v "$ROOT:$ROOT" -v "$PHOREPOC_BUILD:$PHOREPOC_BUILD" -w "$HERE" -e PHOREPOC_BUILD -e PHOREPOC_ARCH \
	"${PHOREPOC_IMAGE:-ghcr.io/phorepoc/base:latest}" bash -c 'set -e; bash recipes/fetch.sh; bash recipes/generate.sh'
