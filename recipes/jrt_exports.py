#!/usr/bin/env python3
# Copyright The Phorepoc Authors
# SPDX-License-Identifier: Apache-2.0
"""jrt_exports -- the header exports of JRT's build, done in the fetched tree (what `sbs` did from each exports.inf).

Every component's build/exports.inf lists PRJ_EXPORTS lines `<source> <destination>`, relative to that file:
  * `|<path>` destinations copy a header to a shared include directory INSIDE the tree (most of them: <jrt>/inc,
    <jrt>/javaruntimes/inc, <jrt>/javauis/inc ...), which the generated mmps reach through omj.pri's ancestor `inc` dirs;
  * `/epoc32/include/<path>` destinations go to <out>/include/<path> (the generated mmps add it as a SYSTEMINCLUDE).
Other destinations (ROM data, emulator trees, iby macros) are left out. The .inf files are run through cpp with the
tree's build_defines.hrh, from which the Qt-era defines are dropped first (the same set jrt_pro2mmp.py drops).

  python3 recipes/jrt_exports.py --jrt <JRT tree> --out <dir>
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys

QT_DEFINES = ("RD_JAVA_UI_QT", "RD_JAVA_APPLICATION_SETTINGS_QT", "OPENLCDUI_ENABLED", "RD_JAVA_OPENLCDUI_ENABLED",
              "RD_JAVA_STDCPPV5")
SKIP_DIRS = ("_qt", ".git", "tsrc", "qt")


def drop_qt_defines(jrt: str) -> None:
    p = os.path.join(jrt, "inc", "build_defines.hrh")
    lines = open(p, encoding="latin-1").read().splitlines(True)
    keep = [ln for ln in lines if not re.match(r"\s*#define\s+(%s)\b" % "|".join(QT_DEFINES), ln)]
    if keep != lines:
        open(p, "w", encoding="latin-1", newline="").write("".join(keep))


def exports_of(inf: str) -> list[tuple[str, str]]:
    text = subprocess.run(["cpp", "-P", "-undef", "-nostdinc", "-traditional-cpp", "-I", os.path.dirname(inf), inf],
                          capture_output=True, text=True, encoding="latin-1").stdout
    out, section = [], None
    for ln in text.splitlines():
        ln = ln.split("//")[0].strip()
        if not ln:
            continue
        if ln.upper().startswith("PRJ_"):
            section = ln.upper()
            continue
        if section != "PRJ_EXPORTS":
            continue
        w = ln.split()
        if len(w) >= 2:
            out.append((w[0], w[1]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jrt", required=True)
    ap.add_argument("--out", required=True, help="where /epoc32/include exports go (<out>/include)")
    a = ap.parse_args()
    drop_qt_defines(a.jrt)
    n_tree = n_epoc = 0
    for dp, dns, fs in os.walk(a.jrt):
        dns[:] = sorted(d for d in dns if d not in SKIP_DIRS and not d.endswith("_qt"))
        if "exports.inf" not in fs:
            continue
        inf = os.path.join(dp, "exports.inf")
        for src, dst in exports_of(inf):
            s = os.path.normpath(os.path.join(dp, src.replace("\\", "/")))
            d = dst.replace("\\", "/")
            if d.startswith("|"):
                t = os.path.normpath(os.path.join(dp, d[1:]))
                n_tree += 1
            elif d.lower().startswith("/epoc32/include/"):
                t = os.path.join(a.out, "include", d[len("/epoc32/include/"):])
                n_epoc += 1
            else:
                continue
            if not os.path.isfile(s) or not s.lower().endswith((".h", ".hrh", ".inl", ".rh", ".loc", ".pan")):
                continue
            os.makedirs(os.path.dirname(t), exist_ok=True)
            if os.path.abspath(s) != os.path.abspath(t):
                shutil.copyfile(s, t)
    print(f"jrt_exports: {n_tree} into the tree, {n_epoc} into {a.out}/include")
    return 0


if __name__ == "__main__":
    sys.exit(main())
