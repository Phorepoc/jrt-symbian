#!/usr/bin/env python3
# Copyright The Phorepoc Authors
# SPDX-License-Identifier: Apache-2.0
"""build_jars -- TEMPORARY (until P2): the Java side of the layer, one jar per JRT DLL, compiled with a host JDK.

The original build romized the classes into each DLL with a closed tool; the replacement VM loads jars instead. Until the
VM's own CLDC class library exists (P2), the classes are compiled against the JDK 8 API (`--release 8`, the oldest a
current javac emits) plus our stand-ins for the VM vendor's API (recipes/java/j9api: com.ibm.oti.*, the GCF base). The
stand-ins are compile-only: they are not in any jar. P2 replaces this with a compile against the VM's CLDC library + a
preverifier pass.

  python3 recipes/build_jars.py --jrt <JRT tree> --out <dir>     (needs javac + jar on PATH)
Writes <out>/<dll name>.jar and <out>/javac.log.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# jar (= the DLL whose natives the classes use) -> its source dirs in the tree
JARS = {
    "javautils": ["javacommons/utils/javasrc", "javacommons/utils/javasrc.s60", "javacommons/jvms/cldc_1.1.1/javasrc"],
    "javastorage": ["javacommons/javastorage/javasrc", "javacommons/javastorage/javasrc.s60"],
    "javacomms": ["javacommons/comms/javasrc"],
    "javafileutils": ["javacommons/fileutils/javasrc", "javacommons/fileutils/javasrc.s60"],
    "javagcf": ["javacommons/gcfbase/javasrc", "javacommons/gcfbase/javasrc.s60"],
    "javafile": ["javacommons/gcfprotocols/file/javasrc", "javacommons/gcfprotocols/file/javasrc.s60"],
    # (PackageProtector, which MidletLifeCycle imports, exists only in the .cdc variant)
    "javasecurity": ["javacommons/security/javasrc", "javacommons/security/javasrc.s60", "javacommons/security/javasrc.cdc"],
    "javaconnectionmanager": ["javacommons/connectionmanager/javasrc.s60"],
    "javamidpruntime": ["javaruntimes/midp/runtime/javasrc"],
    "javacoreui": ["javauis/coreui_akn/javasrc"],
    "javaruntimeui": ["javauis/runtimeui_akn/javasrc", "javauis/runtimeui_akn/javasrc.s60"],
    "javalcdui": ["javauis/lcdui_akn/javalcdui/javasrc", "javauis/lcdui_akn/javalcdui/javasrc.nokialcdui"],
    "javarms": ["javaextensions/midprms_db/javasrc"],
    "javalegacyutils": ["javauis/javalegacyutils/javasrc"],
    "eswt": ["javauis/eswt_akn/org.eclipse.ercp.swt.s60/src", "javauis/eswt_akn/org.eclipse.ercp.swt.s60/src-j2me",
             "javauis/eswt_akn/org.eclipse.ercp.swt.core.common/SWT-common",
             "javauis/eswt_akn/org.eclipse.ercp.swt.core.common/SWT-common-j2me",
             "javauis/eswt_akn/org.eclipse.ercp.swt.expanded.common/Eclipse-SWT-common"],
    "eswtdirectcontent": ["javauis/eswt_akn/eswtdirectcontent/src"],
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jrt", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    classes = os.path.join(out, "classes")
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(classes)
    owner: dict[str, str] = {}          # "pkg/Class" (source path without .java) -> jar
    srcs: list[str] = []
    for jar, dirs in JARS.items():
        for d in dirs:
            root = os.path.join(a.jrt, d)
            for dp, dns, fs in os.walk(root):
                dns[:] = [x for x in dns if x != "tsrc"]
                for f in fs:
                    if f.endswith(".java"):
                        p = os.path.join(dp, f)
                        rel = os.path.relpath(p, root)[:-5].replace(os.sep, "/")
                        if rel not in owner:
                            owner[rel] = jar
                            srcs.append(p)
    open(os.path.join(out, "sources.txt"), "w").write("\n".join(srcs) + "\n")
    # compile-only: the VM API stand-ins, and MMAPI's classes (eswtdirectcontent names its control interfaces)
    sp = os.pathsep.join([os.path.join(a.jrt, d) for ds in JARS.values() for d in ds]
                         + [os.path.join(a.jrt, "javauis/mmapi_akn/javasrc"), os.path.join(HERE, "java/j9api")])
    # javac writes no class while any file has an error, so a file that does not compile against the JDK stand-in
    # (one so far: EventProcessor's `super(null, name)` is ambiguous between Thread(ThreadGroup,String) and
    # Thread(Runnable,String); CLDC has only the second) is left out and named in excluded.txt -- P2 compiles against CLDC
    excluded: list[str] = []
    for _ in range(10):
        live = [s for s in srcs if s not in excluded]
        open(os.path.join(out, "sources.txt"), "w").write("\n".join(live) + "\n")
        with open(os.path.join(out, "javac.log"), "w") as log:
            r = subprocess.run(["javac", "--release", "8", "-nowarn", "-encoding", "ISO-8859-1", "-Xmaxerrs", "5000",
                                "-implicit:none", "-sourcepath", sp, "-d", classes, "@" + os.path.join(out, "sources.txt")],
                               stdout=log, stderr=subprocess.STDOUT)
        if r.returncode == 0:
            break
        bad = {ln.split(".java:")[0] + ".java" for ln in open(os.path.join(out, "javac.log")) if ".java:" in ln and ": error:" in ln}
        bad = [b for b in bad if b in srcs and b not in excluded]
        if not bad:
            break
        excluded += bad
    open(os.path.join(out, "excluded.txt"), "w").write("".join(e + "\n" for e in excluded))
    errors = sum(1 for ln in open(os.path.join(out, "javac.log")) if ": error:" in ln)
    # split the classes by the source they came from (Outer$Inner.class -> Outer)
    per: dict[str, list[str]] = {}
    for dp, _, fs in os.walk(classes):
        for f in fs:
            if f.endswith(".class"):
                rel = os.path.relpath(os.path.join(dp, f), classes).replace(os.sep, "/")
                per.setdefault(owner.get(rel[:-6].split("$")[0], "jrt-misc"), []).append(rel)
    for jar, files in sorted(per.items()):
        subprocess.run(["jar", "cf", os.path.join(out, jar + ".jar"), *sum((["-C", classes, f] for f in sorted(files)), [])],
                       check=True)
        print(f"{jar}.jar: {len(files)} classes")
    print(f"build_jars: {len(srcs)} sources, {len(excluded)} left out (excluded.txt), javac exit {r.returncode}, {errors} errors")
    return 0


if __name__ == "__main__":
    sys.exit(main())
