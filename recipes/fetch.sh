#!/usr/bin/env bash
# Copyright The Phorepoc Authors
# SPDX-License-Identifier: Apache-2.0

# recipes/fetch.sh -- fetch what jrt.lock pins into $PHOREPOC_BUILD/jrt: the JRT tree at its commit (src/, shallow, by
# sha) and jni.h (epoc32/include/jni.h, checked by SHA-256). Safe to re-run: a tree already at its commit is reset to it
# (the generated files in it are made again by prepare.sh).
set -eu
: "${PHOREPOC_BUILD:?}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$PHOREPOC_BUILD/jrt"
mkdir -p "$OUT/epoc32/include"
pin() { awk -v n="$1" -F'\t' '!/^#/ && $1 == n { print $2 "\t" $3 }' "$HERE/jrt.lock"; }

IFS="$(printf '\t')" read -r url commit <<EOF
$(pin jrt)
EOF
# under its package name: the pdk builds oss.FCL.sf.app.* code under the S60 product variant (bldvariant.hrh: the
# platform R&D flags RD_SCALABLE_UI_V2, RD_TACTILE_FEEDBACK ...), as the 2010 build did for this app-layer package
src="$OUT/oss.FCL.sf.app.JRT"
[ -d "$src/.git" ] || git init -q "$src"
if [ "$(git -C "$src" rev-parse HEAD 2>/dev/null)" != "$commit" ]; then
	echo "fetch jrt @ ${commit%"${commit#????????}"}"
	git -C "$src" fetch -q --depth 1 "$url" "$commit"
fi
git -C "$src" checkout -q --force "$commit"
git -C "$src" clean -q -fdx

IFS="$(printf '\t')" read -r url sum <<EOF
$(pin jni.h)
EOF
jni="$OUT/epoc32/include/jni.h"
if [ ! -f "$jni" ]; then
	curl -fsSL "$url" | base64 -d > "$jni.tmp"
	echo "$sum  $jni.tmp" | sha256sum -c --status || { echo "jni.h: SHA-256 mismatch" >&2; rm -f "$jni.tmp"; exit 1; }
	# the one change: C++ jweak as its own class derived from _jobject (the VM vendor's header did this, and eSWT
	# declares `class _jweak; typedef _jweak* TSwtPeer` against it); C keeps `typedef jobject jweak`
	sed -i 's|^typedef _jobject\*       jweak;|class _jweak : public _jobject {};\ntypedef _jweak*         jweak;|' "$jni.tmp"
	grep -q '^class _jweak' "$jni.tmp" || { echo "jni.h: the jweak line moved" >&2; exit 1; }
	# ... and the C++ structs under Sun's names (JNIEnv_, JavaVM_), which the VM vendor's header kept: JRT's frozen .def
	# files name them in mangled exports (JniUtils::jstringToWstring(JNIEnv_*, ...)), so the ABI needs these names
	sed -i 's/_JNIEnv/JNIEnv_/g; s/_JavaVM/JavaVM_/g' "$jni.tmp"
	mv "$jni.tmp" "$jni"
fi
echo "jrt: $(git -C "$src" log --oneline -1)"
