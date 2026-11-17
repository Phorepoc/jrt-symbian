#!/usr/bin/env python3
# Copyright The Phorepoc Authors
# SPDX-License-Identifier: Apache-2.0
"""jrt_pro2mmp -- turn JRT's qmake .pro files (Avkon-era tree, jrt.lock) into the .mmp files the pdk's build_mmp_x32 builds.

JRT 2.x is built by qmake (`CONFIG += omj java`, build/omj.pri), which writes the .mmp; the pdk has no qmake.
This evaluates the subset of qmake those .pro/.pri files use (assignments, `symbian {}` / `!symbian {}` / contains()
/ isEmpty() / exists() scopes, `else`, `cond: stmt`, include()) for the Symbian target and emits the mmp qmake would
have written, plus what omj.pri adds to every `CONFIG += java` component:

  * lookup.cpp -- the JNI name table (the format of build/buildutils/generates60lookup.py): `jni_lookup(const char*)`
    = EXPORT ordinal 1, how the VM binds Java natives in a Symbian DLL. The J9GetJXE getter is kept, pointing at jxe.c.
  * jxe.c -- the romized-class image of the original VM (made by a closed tool). An EMPTY `j9Jar[]` here, as Nokia's
    own createstubfiles.py does for builds without that tool: a replacement VM loads the classes from jars.
  * the javah headers the sources include (javah_standin): written from the sources themselves (the JNI functions
    they define + the class's constants from its .java), so the build needs no Java compiler. --javah <dir> uses real
    javah output instead.

PROJECT_DEFINES: build_defines.pri in the tree is the Qt-era generated file; the Avkon build drops the Qt defines
(RD_JAVA_UI_QT, RD_JAVA_APPLICATION_SETTINGS_QT, OPENLCDUI_ENABLED, RD_JAVA_OPENLCDUI_ENABLED).

  python3 recipes/jrt_pro2mmp.py --jrt <JRT tree> [pro ...]      (no pro: the COMPONENTS list below)
Writes <pro dir>/<target>.mmp and <pro dir>/phorepoc_gen/{lookup.cpp,jxe.c,*.h}.
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import sys

SYSINC: list[str] = []
# the Qt-era defines, and RD_JAVA_STDCPPV5: the image's Open C++ is libstdcpp + STLport (OS_LAYER_STDCPP_SYSTEMINCLUDE,
# omj.pri's other branch); STLport 5 / libstdcppv5 is not built
QT_DEFINES = {"RD_JAVA_UI_QT", "RD_JAVA_APPLICATION_SETTINGS_QT", "OPENLCDUI_ENABLED", "RD_JAVA_OPENLCDUI_ENABLED",
              "RD_JAVA_STDCPPV5"}

# the components built from a .pro (the minimal MIDP set, what its LIBS pull in, and eSWT)
COMPONENTS = [
    "javacommons/jvms/nativeportlayer/build/jvmnativeport.pro",
    "javacommons/utils/build/javautils.pro",
    "javacommons/javastorage/build/javastorage.pro",
    "javacommons/comms/build/comms.pro",
    "javacommons/comms/ipclib/clientserver/build/ipc.pro",
    "javacommons/fileutils/build/fileutils.pro",
    "javacommons/gcfprotocols/file/build/javafile.pro",
    "javaruntimes/midp/runtime/build/javamidpruntime.pro",
    "javaruntimes/midp/runtimestarter/build/javamidpstarter.pro",
    "javaruntimes/standalone/build/javastarter.pro",
    "javaruntimes/starterutils/build/javaruntimestarterutils.pro",
    "javaruntimes/jvmargmodifier/default/build/javajvmargsmodifier.pro",
    "javauis/lcdui_akn/javalcdui/build/javalcdui.pro",
    "javauis/coreui_akn/build/javacoreui.pro",
    "javauis/runtimeui_akn/build/javaruntimeui.pro",
    "javauis/javalegacyutils/build/javalegacyutils.pro",
    "javaextensions/midprms_db/build/javarms.pro",
    "javacommons/javaenv/build/javaenv.pro",
    "javacommons/security/build/javasecurity.pro",
    "javacommons/gcfbase/build/javagcf.pro",
    "javacommons/connectionmanager/build/javaconnectionmanager.pro",
    "javauis/eswt_akn/org.eclipse.ercp.swt.s60/native/build/eswt.pro",
    "javauis/eswt_akn/eswtdirectcontent/build/eswtdirectcontent.pro",
    "javauis/remconobserver_akn/build/javaremconobserver.pro",
]


class Pro:
    def __init__(self, jrt: str, pro: str):
        self.jrt = jrt
        self.pro = os.path.abspath(pro)
        self.pwd = os.path.dirname(self.pro)
        self.v: dict[str, list[str]] = {"CONFIG": [], "QT": ["core", "gui"], "LIBS": [], "DEFINES": [],
                                        "INCLUDEPATH": [], "SOURCES": [], "MMP_RULES": [], "PROJECT_DEFINES": []}
        self.funcs = {}

    # ---- expression helpers
    def expand(self, s: str) -> str:
        s = s.replace("$${LITERAL_HASH}", "#").replace("$$LITERAL_HASH", "#")
        s = s.replace("$${_PRO_FILE_PWD_}", self.pwd).replace("$$_PRO_FILE_PWD_", self.pwd)
        s = re.sub(r"\$\$unique\((\w+)\)", lambda m: " ".join(dict.fromkeys(self.v.get(m.group(1), []))), s)
        s = re.sub(r"\$\$\(([A-Z_]+)\)", "", s)                       # environment: empty on our host
        s = re.sub(r"\$\$\{(\w+(?:\.\w+)?)\}", lambda m: " ".join(self.v.get(m.group(1), [])), s)
        s = re.sub(r"\$\$(\w+(?:\.\w+)?)", lambda m: " ".join(self.v.get(m.group(1), [])), s)
        return s

    def words(self, s: str) -> list[str]:
        out = re.findall(r'"[^"]*"|\S+', self.expand(s))
        return [w[1:-1] if w.startswith('"') and w.endswith('"') else w for w in out]

    def test(self, cond: str) -> bool:
        cond = cond.strip()
        if "|" in cond and not cond.startswith(("contains", "!contains", "exists", "isEmpty")):
            return any(self.test(c) for c in cond.split("|"))
        if ":" in cond:
            return all(self.test(c) for c in cond.split(":"))
        neg = cond.startswith("!")
        c = cond[1:] if neg else cond
        m = re.match(r"(\w+)\((.*)\)$", c)
        if m:
            fn, args = m.group(1), [a.strip() for a in m.group(2).split(",")]
            if fn == "contains":
                vals = self.v.get(args[0], [])
                r = args[1] in vals or (args[0] == "TARGET" and args[1] == " ".join(vals))
            elif fn == "isEmpty":
                r = not self.v.get(args[0])
            elif fn == "exists":
                r = os.path.exists(self.expand(args[0]))
            elif fn == "equals":
                r = " ".join(self.v.get(args[0], [])) == args[1]
            else:
                r = False
        elif c == "symbian":
            r = True
        elif c in ("debug", "win32", "unix", "linux-g++"):
            r = False
        elif c == "release":
            r = True
        else:
            r = c in self.v["CONFIG"]
        return not r if neg else r

    def assign(self, stmt: str):
        m = re.match(r"([\w.]+)\s*(\+=|-=|\*=|=|~=)\s*(.*)$", stmt)
        if not m:
            m2 = re.match(r"(\w+)\((.*)\)$", stmt.strip())
            if m2 and m2.group(1) == "include":
                self.include(self.expand(m2.group(2)).strip())
            return
        var, op, rhs = m.groups()
        w = self.words(rhs)
        cur = self.v.setdefault(var, [])
        if op == "=":
            self.v[var] = w
        elif op == "+=":
            cur.extend(w)
        elif op == "*=":
            cur.extend(x for x in w if x not in cur)
        elif op == "-=":
            self.v[var] = [x for x in cur if x not in w]

    def include(self, rel: str):
        p = rel if os.path.isabs(rel) else os.path.normpath(os.path.join(self.cur_dir, rel))
        if os.path.isfile(p):
            self.run_file(p)


    def pro_ifdefs(self, text: str) -> str:
        """Some .pro files wrap LIBS lines in C-preprocessor #ifdef blocks (javalcdui: `-llibegl -llibglesv1_cm` under
        #ifdef RD_JAVA_NGA_ENABLED, after a LIBS list). To qmake `#` starts a comment, so the lines in between belong to
        the open LIBS continuation. Honoured here against PROJECT_DEFINES: an active block's `-l` lines become
        `LIBS += ...`, an inactive block is dropped."""
        out, stack = [], []
        for ln in text.splitlines():
            m = re.match(r"\s*#\s*(ifdef|ifndef|else|endif)\b\s*(\w*)", ln)
            if m:
                kw, name = m.groups()
                if kw in ("ifdef", "ifndef"):
                    on = (name in self.v.get("PROJECT_DEFINES", [])) == (kw == "ifdef")
                    stack.append(on)
                elif kw == "else" and stack:
                    stack[-1] = not stack[-1]
                elif kw == "endif" and stack:
                    stack.pop()
                out.append("")
                continue
            if stack:
                if not all(stack):
                    out.append("")
                    continue
                if re.match(r"\s*-l\S", ln):
                    ln = "LIBS += " + ln.strip().rstrip("\\").strip()
            out.append(ln)
        return "\n".join(out) + "\n"

    # ---- the interpreter: lines -> blocks
    def run_file(self, path: str):
        save = getattr(self, "cur_dir", self.pwd)
        self.cur_dir = os.path.dirname(path)
        text = open(path, encoding="latin-1").read()
        text = self.pro_ifdefs(text)
        text = re.sub(r"\\[ \t]*\r?\n", " ", text)
        lines = [re.sub(r"(^|\s)#.*$", "", ln).strip() for ln in text.splitlines()]
        toks = []
        for ln in lines:                                   # split braces into their own tokens
            if not ln:
                continue
            for part in re.split(r"(\{|\})", ln):
                if part.strip():
                    toks.append(part.strip())
        self.exec_tokens(toks, 0, True)
        self.cur_dir = save

    def exec_tokens(self, toks, i, active, single=False):
        last = None
        while i < len(toks):
            t = toks[i]
            if t == "}":
                return i + 1, last
            if i + 1 < len(toks) and toks[i + 1] == "{":           # `cond {`
                cond = t.rstrip(":").strip()
                if cond.startswith("defineReplace") or cond.startswith("for("):
                    i = self.skip(toks, i + 2)
                    continue
                if cond in ("else", "} else"):
                    r = active and last is False
                elif cond.startswith("else:"):
                    r = active and last is False and self.test(cond[5:])
                else:
                    r = active and self.test(cond)
                i, _ = self.exec_tokens(toks, i + 2, r)
                last = r if cond == "else" or not cond.startswith("else") else (last or r)
                continue
            # `cond: stmt` / `cond: stmt` chains; `else: stmt`
            m = re.match(r"^((?:!?[\w-]+(?:\([^()]*\))?\s*[:|]\s*)+)(.*)$", t)
            if m and not re.match(r"^[\w.]+\s*(\+=|-=|\*=|=)", t):
                conds, stmt = m.group(1).strip().rstrip(":").strip(), m.group(2)
                if conds == "else":
                    r = active and last is False
                elif conds.startswith("else:"):
                    r = active and last is False and self.test(conds[5:])
                else:
                    r = active and self.test(conds)
                if r:
                    self.assign(stmt)
                last = r if not conds.startswith("else") else (last or r)
                i += 1
                continue
            if active:
                self.assign(t)
            i += 1
        return i, last

    def skip(self, toks, i):
        depth = 1
        while i < len(toks) and depth:
            depth += {"{": 1, "}": -1}.get(toks[i], 0)
            i += 1
        return i


def project_defines(jrt: str) -> list[str]:
    t = open(os.path.join(jrt, "inc", "build_defines.pri"), encoding="latin-1").read()
    m = re.search(r"PROJECT_DEFINES\s*\*=\s*(.*)", t)
    return [d for d in m.group(1).split() if d not in QT_DEFINES]


def convert(jrt: str, pro_path: str, javah: str | None) -> dict:
    p = Pro(jrt, pro_path)
    p.v["PROJECT_DEFINES"] = project_defines(jrt)
    p.v["_SKIP_BUILD_DEFINES"] = ["1"]
    p.run_file(p.pro)
    # build_defines.pri re-includes would re-add the Qt defines
    p.v["PROJECT_DEFINES"] = [d for d in p.v["PROJECT_DEFINES"] if d not in QT_DEFINES]
    tgt = p.v.get("TARGET", ["?"])[0]
    tmpl = p.v.get("TEMPLATE", ["lib"])[0]
    gen = os.path.join(p.pwd, "phorepoc_gen")
    os.makedirs(gen, exist_ok=True)

    srcs = []
    for s in p.v["SOURCES"]:
        a = s if os.path.isabs(s) else os.path.join(p.pwd, s)
        hits = sorted(glob.glob(a)) if any(c in a for c in "*?") else [a]
        srcs.extend(os.path.normpath(h) for h in hits if h.endswith((".cpp", ".c", ".cia")))
    if not srcs and "javaonly" not in p.v["CONFIG"]:
        # omj.pri findfiles(): ../src and ../src.s60, *.cpp there and one directory level below
        for sd in ("src", "src.s60"):
            base = os.path.join(p.pwd, "..", sd)
            srcs += sorted(glob.glob(os.path.join(base, "*.cpp"))) + sorted(glob.glob(os.path.join(base, "*", "*.cpp")))
        srcs = [os.path.normpath(s) for s in srcs]
    srcs = list(dict.fromkeys(srcs))
    incs = [os.path.normpath(i if os.path.isabs(i) else os.path.join(p.pwd, i)) for i in p.v["INCLUDEPATH"]
            if not i.startswith("$") and "epoc32" not in i]
    incs = [i for i in dict.fromkeys(incs) if os.path.isdir(i)]
    libs = [w[2:].lower() for w in p.v["LIBS"] if w.startswith("-l")]
    libs = list(dict.fromkeys(libs))
    defines = [d for d in dict.fromkeys(p.v["DEFINES"] + p.v["PROJECT_DEFINES"]) if d not in QT_DEFINES]
    is_java = "java" in p.v["CONFIG"]
    std = "stdbinary" in p.v["CONFIG"]
    uid2 = (p.v.get("TARGET.UID2") or ["0x20004c45" if std else ("0x1000008d" if tmpl == "lib" else "0x100039ce")])[0]
    uid3 = (p.v.get("TARGET.UID3") or ["0"])[0]
    caps = " ".join(p.v.get("TARGET.CAPABILITY") or (["all", "-tcb"] if tmpl == "lib" else []))

    rel = lambda path: os.path.relpath(path, p.pwd).replace("\\", "/")
    out = [f"// generated by jrt_pro2mmp.py from {os.path.basename(p.pro)} (qmake stand-in, do not edit)",
           "#include <platform_paths.hrh>",
           f"TARGET {tgt}.{'exe' if tmpl == 'app' else 'dll'}",
           f"TARGETTYPE {'exe' if tmpl == 'app' else ('stddll' if std else 'dll')}",
           f"UID {uid2} {uid3}"]
    if caps:
        out.append(f"CAPABILITY {caps}")
    for k in ("TARGET.EPOCHEAPSIZE", "TARGET.EPOCSTACKSIZE"):
        if p.v.get(k):
            out.append(f"{k.split('.')[1]} {' '.join(p.v[k])}")
    out.append("EPOCALLOWDLLDATA")
    for d in defines:
        out.append(f"MACRO {d}")
    out += ["MACRO __SYMBIAN32__", "MACRO J9EPOC32", "MACRO RD_JAVA_OMJ_FSERVER"]
    out += ["APP_LAYER_SYSTEMINCLUDE", "OS_LAYER_LIBC_SYSTEMINCLUDE", "OS_LAYER_SSL_SYSTEMINCLUDE"]
    if "stl" in p.v["CONFIG"]:
        out.append("OS_LAYER_STDCPP_SYSTEMINCLUDE")
    # omj.pri INC_DIRS: ../inc.s60, each ancestor `inc` up to the tree root, the source dirs
    inc_dirs = []
    if os.path.isdir(os.path.join(p.pwd, "..", "inc.s60")):
        inc_dirs.append(os.path.normpath(os.path.join(p.pwd, "..", "inc.s60")))
    d = p.pwd
    while os.path.normpath(d) != os.path.normpath(jrt) and len(d) > len(jrt):
        d = os.path.dirname(d)
        if os.path.isdir(os.path.join(d, "inc")):
            inc_dirs.append(os.path.normpath(os.path.join(d, "inc")))
    inc_dirs += sorted({os.path.dirname(s) for s in srcs})
    for i in dict.fromkeys(incs + inc_dirs):
        out.append(f"USERINCLUDE {rel(i)}")
    out.append("SYSTEMINCLUDE phorepoc_gen")          # javah headers (omj.pri: SYSTEMINCLUDE $JAVAH_INCLUDE_PATH)
    for d in SYSINC:                                  # the tree's /epoc32/include exports + jni.h (recipes/prepare.sh)
        out.append(f"SYSTEMINCLUDE {rel(d)}")
    if not std and tmpl == "lib":
        out.append(f"DEFFILE ./~/{tgt}.def")
    by_dir: dict[str, list[str]] = {}
    for s in srcs:
        by_dir.setdefault(os.path.dirname(s), []).append(os.path.basename(s))
    for dd, files in by_dir.items():
        out.append(f"SOURCEPATH {rel(dd)}")
        out += [f"SOURCE {f}" for f in files]
    jni = []
    if not is_java:
        # no JNI table, but its sources may still include a javah header for a class's constants
        javah_standin(jrt, gen, srcs, [])
    if is_java:
        ACTIVE_DEFINES.clear()
        ACTIVE_DEFINES.update(set(defines) | PLATFORM_DEFINES | {"__SYMBIAN32__", "J9EPOC32", "RD_JAVA_OMJ_FSERVER"})
        jni = write_lookup(p, gen, javah, srcs, jrt)
        out += ["SOURCEPATH phorepoc_gen", "SOURCE lookup.cpp", "SOURCE jxe.c"]
    for lib in libs:
        out.append(f"LIBRARY {lib}.lib")
    # qmake's Symbian defaults (the mkspec's LIBS: Open C + euser), and Open C++ for `CONFIG += stl`
    for lib in ["euser", "libc", "libm", "libdl", "libpthread"] + (["libstdcpp"] if "stl" in p.v["CONFIG"] else []):
        if lib not in libs:
            out.append(f"LIBRARY {lib}.lib")
    out.append("PAGED")
    mmp = os.path.join(p.pwd, f"{tgt}.mmp")
    open(mmp, "w", newline="\n").write("\n".join(out) + "\n")
    return dict(target=tgt, mmp=mmp, sources=len(srcs), libs=libs, java=is_java, jni=len(jni),
                missing=[s for s in srcs if not os.path.isfile(s)])


def java_classes_of(pwd: str) -> set[str]:
    """Fully qualified classes under this component's ../javasrc* (excluding linux/cdc variants)."""
    root = os.path.dirname(pwd)
    out = set()
    for jd in glob.glob(os.path.join(root, "javasrc*")):
        if jd.endswith((".linux", ".cdc")):
            continue
        for dp, _, fs in os.walk(jd):
            for f in fs:
                if f.endswith(".java"):
                    out.add(os.path.relpath(os.path.join(dp, f[:-5]), jd).replace(os.sep, "."))
    return out


RE_JNIDECL = re.compile(r"JNIEXPORT\s+\w+\s+JNICALL\s+(\w+)\s*\n?\s*\(")
# a JNI function DEFINITION in a component's C++ (return type, name, parameter list)
RE_JNIDEF = re.compile(r"JNIEXPORT\s+([\w\s\*]+?)\s+JNICALL\s+(Java_\w+)\s*\(([^)]*)\)\s*\{")
RE_JAVAH_INC = re.compile(r'#\s*include\s*[<"]((?:com|javax|org)_\w+)\.h[>"]')
_JAVA_INDEX: dict[str, str] = {}


def mangle(fqcn: str) -> str:
    """JNI name mangling of a class name (JNI spec: '_' -> _1, '$' -> _00024, '.' -> _)."""
    return fqcn.replace("_", "_1").replace("$", "_00024").replace(".", "_")


def java_index(jrt: str) -> dict[str, str]:
    """Mangled top-level class name -> its .java file, over the whole tree (no tests, no Linux/CDC/Qt variants)."""
    if _JAVA_INDEX:
        return _JAVA_INDEX
    for dp, dns, fs in os.walk(jrt):
        dns[:] = [d for d in dns if d not in (".git", "tsrc") and not d.endswith((".linux", ".cdc", "_qt"))]
        if "javasrc" not in dp:
            continue
        for f in fs:
            if not f.endswith(".java"):
                continue
            path = os.path.join(dp, f)
            m = re.search(r"^\s*package\s+([\w.]+)\s*;", open(path, encoding="latin-1").read(), re.M)
            fq = (m.group(1) + "." if m else "") + f[:-5]
            _JAVA_INDEX.setdefault(mangle(fq), path)
    return _JAVA_INDEX


def _strip_java_comments(s: str) -> str:
    return re.sub(r"//[^\n]*|/\*.*?\*/", " ", s, flags=re.S)


def java_constants(path: str, prefix: str) -> list[str]:
    """The `#define <class>_<NAME> <value>` lines javah writes for a class's static final primitive constants.
    Values are evaluated from the Java source (literals, other constants of the class, + - * << >> | & ~ and casts);
    a constant whose initialiser is not a compile-time constant we can evaluate is left out (a compile then names it)."""
    body = _strip_java_comments(open(path, encoding="latin-1").read())
    vals: dict[str, object] = {}
    out = []
    pat = re.compile(r"\b((?:(?:public|private|protected|static|final|transient|volatile)\s+)+)"
                     r"(int|long|short|byte|char|boolean|float|double)\s+(\w+)\s*=\s*([^;]+);")
    for mods, typ, name, expr in pat.findall(body):
        if "static" not in mods or "final" not in mods:
            continue
        e = expr.strip()
        e = re.sub(r"\((?:int|long|short|byte|char)\)", "", e)
        e = re.sub(r"'\\?(.)'", lambda m: str(ord(m.group(1))), e)
        e = re.sub(r"\b(0[xX][0-9a-fA-F]+|\d+)[lL]\b", r"\1", e)
        e = re.sub(r"\b(\d+\.\d*|\d*\.\d+)[fFdD]?\b", r"\1", e)
        e = e.replace("true", "1").replace("false", "0").replace(">>>", ">>")
        e = re.sub(r"\b([A-Za-z_]\w*)\b", lambda m: repr(vals[m.group(1)]) if m.group(1) in vals else m.group(1), e)
        if re.search(r"[A-Za-z_\"]", re.sub(r"0[xX][0-9a-fA-F]+", "", e)):
            continue
        try:
            v = eval(e, {"__builtins__": {}})          # noqa: S307 -- arithmetic over literals only (checked above)
        except Exception:                               # noqa: BLE001
            continue
        if typ in ("float", "double"):
            vals[name] = float(v)
            out.append(f"#define {prefix}_{name} {float(v)!r}{'f' if typ == 'float' else ''}")
            continue
        v = int(v)
        bits = 64 if typ == "long" else 32
        v &= (1 << bits) - 1
        if v >> (bits - 1):
            v -= 1 << bits
        vals[name] = v
        out.append(f"#define {prefix}_{name} {v}{'LL' if typ == 'long' else 'L'}")
    return out


def javah_standin(jrt: str, gen: str, srcs: list[str], defs: list[tuple[str, str, str]]) -> list[str]:
    """Write the javah headers this component's sources include, from the sources themselves: the prototypes of the
    JNI functions they define (extern "C", as javah declares them) and the class's constants (java_constants).
    Nokia's build ran javah on the compiled classes; this needs no Java compiler."""
    wanted = set()
    for s in srcs:
        if os.path.isfile(s):
            wanted.update(RE_JAVAH_INC.findall(open(s, encoding="latin-1").read()))
    # headers next to the sources and in the component's inc dirs that include javah headers themselves
    for d in {os.path.dirname(s) for s in srcs} | {os.path.join(os.path.dirname(os.path.dirname(s)), "inc") for s in srcs}:
        for h in glob.glob(os.path.join(d, "*.h")):
            wanted.update(RE_JAVAH_INC.findall(open(h, encoding="latin-1").read()))
    index = java_index(jrt)
    written = []
    for h in sorted(wanted):
        protos = [f"JNIEXPORT {r} JNICALL {n}({a});" for r, n, a in defs
                  if n.startswith(f"Java_{h}_") and not n[len(h) + 6:][:1].isdigit()]
        consts = java_constants(index[h], h) if h in index else []
        guard = f"_Included_{h}"
        lines = [f"/* generated by jrt_pro2mmp.py (javah stand-in) for class {h} */", "#include <jni.h>",
                 f"#ifndef {guard}", f"#define {guard}"] + consts + \
                ["#ifdef __cplusplus", 'extern "C" {', "#endif"] + protos + ["#ifdef __cplusplus", "}", "#endif", "#endif"]
        open(os.path.join(gen, h + ".h"), "w", newline="\n").write("\n".join(lines) + "\n")
        written.append(h + ".h")
    return written



# the defines a component is compiled with (its MACROs + the platform's, PLATFORM_DEFINES), for active_text()
ACTIVE_DEFINES: set[str] = set()
PLATFORM_DEFINES: set[str] = set()


def _cond(expr: str, defs: set[str]) -> bool:
    """A preprocessor condition over `defined X` / `!defined X` / && / || / 0 / 1; anything else counts as true
    (a value test we cannot evaluate: keep the code, a link then names it)."""
    e = re.sub(r"defined\s*\(\s*(\w+)\s*\)|defined\s+(\w+)",
               lambda m: "1" if (m.group(1) or m.group(2)) in defs else "0", expr)
    e = e.replace("&&", " and ").replace("||", " or ").replace("!", " not ")
    if re.search(r"[A-Za-z_]\w*", re.sub(r"\b(and|or|not)\b", "", e)):
        return True
    try:
        return bool(eval(e, {"__builtins__": {}}))   # noqa: S307 -- 0/1 and boolean operators only (checked above)
    except Exception:                               # noqa: BLE001
        return True


def active_text(text: str, defs: set[str]) -> str:
    """The text with the #if/#ifdef/#ifndef/#elif/#else blocks that are off for `defs` blanked out, so the JNI table
    lists only the functions the compiler really sees (CMIDTactileFeedback.cpp: all under #ifdef RD_TACTILE_FEEDBACK)."""
    out, stack = [], []          # stack of (this branch on, some branch taken, parent on)
    on = True
    for ln in text.splitlines(True):
        m = re.match(r"\s*#\s*(ifdef|ifndef|if|elif|else|endif)\b(.*)", ln)
        if m:
            kw, rest = m.group(1), m.group(2).split("//")[0].strip()
            if kw in ("ifdef", "ifndef", "if"):
                c = (rest.split()[0] in defs) if kw == "ifdef" else \
                    (rest.split()[0] not in defs) if kw == "ifndef" else _cond(rest, defs)
                stack.append((on, c))
                on = on and c
            elif kw == "elif" and stack:
                parent, taken = stack[-1]
                c = not taken and _cond(rest, defs)
                stack[-1] = (parent, taken or c)
                on = parent and c
            elif kw == "else" and stack:
                parent, taken = stack[-1]
                on = parent and not taken
                stack[-1] = (parent, True)
            elif kw == "endif" and stack:
                on = stack.pop()[0]
            out.append("\n")
            continue
        out.append(ln if on else "\n")
    return "".join(out)


def write_lookup(p: Pro, gen: str, javah: str | None, srcs: list[str], jrt: str) -> list[str]:
    classes = java_classes_of(p.pwd)
    headers, fns, decls = [], [], []
    if javah and os.path.isdir(javah):
        for h in sorted(os.listdir(javah)):
            cls = h[:-2].replace("_", ".")
            if not h.endswith(".h") or not any(cls == c.replace("_", ".") for c in classes):
                continue
            body = open(os.path.join(javah, h)).read()
            names = RE_JNIDECL.findall(body)
            if not names:
                continue
            open(os.path.join(gen, h), "w", newline="\n").write(body)
            headers.append(h)
            fns += names
    else:
        defs = []
        for s in srcs:
            if os.path.isfile(s):
                defs += [(re.sub(r"\s+", " ", r), n, re.sub(r"\s+", " ", a))
                         for r, n, a in RE_JNIDEF.findall(active_text(open(s, encoding="latin-1").read(), ACTIVE_DEFINES))]
        javah_standin(jrt, gen, srcs, defs)
        fns = [n for _, n, _ in defs]
        # C linkage, so a plain declaration names the same symbol whatever the real signature
        decls = [f'extern "C" void {n}();' for n in sorted(set(fns))]
    fns = sorted(set(fns) | {"J9GetJXE"})
    # format of build/buildutils/generates60lookup.py (FuncTable / findMethod from javacommons/utils/inc/jni.h side)
    src = ["/* Automatically generated JNI lookup file (jrt_pro2mmp.py, generates60lookup.py format). */",
           "#include \"javasymbianoslayer.h\"", "typedef void (*TFunc)();",
           "typedef unsigned long long U_64;   /* (the VM vendor's jni.h typedef) */",
           "extern \"C\" {", "    extern const U_64 j9Jar[];",
           "    void* J9GetJXE() { return const_cast<void*>(reinterpret_cast<const void*>(j9Jar)); }", "}"]
    src += [f'#include "{h}"' for h in headers] + decls
    src.append("const FuncTable funcTable[] = {")
    src.append(",\n".join(f'   {{ "{f}", (unsigned int) {f}}}' for f in fns))
    src += ["};", "IMPORT_C TFunc jni_lookup(const char* name);",
            "EXPORT_C TFunc jni_lookup(const char* name) {",
            "    return (TFunc)findMethod(name, funcTable, sizeof(funcTable)/sizeof(FuncTable));", "}"]
    open(os.path.join(gen, "lookup.cpp"), "w", newline="\n").write("\n".join(src) + "\n")
    open(os.path.join(gen, "jxe.c"), "w", newline="\n").write(
        "/* Phorepoc: no J9 romized classes (jar2jxe is closed); the replacement VM loads jars. */\n"
        "typedef unsigned long long U_64;\nconst U_64 j9Jar[] = { 0 };\n")
    return fns


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jrt", required=True, help="the JRT tree (oss.FCL.sf.app.JRT at the commit in jrt.lock)")
    ap.add_argument("--javah", default=None, help="javah headers of the compiled classes; default: the stand-in from the sources")
    ap.add_argument("--sysinc", action="append", default=[], help="an extra SYSTEMINCLUDE dir for every mmp")
    ap.add_argument("--platform-hrh", action="append", default=[],
                    help="a platform .hrh whose #defines every component is compiled with (bldcodeline.hrh)")
    ap.add_argument("pros", nargs="*")
    a = ap.parse_args()
    SYSINC.extend(os.path.abspath(d) for d in a.sysinc)
    for h in a.platform_hrh:
        for m in re.finditer(r"^\s*#define\s+(\w+)", open(h, encoding="latin-1").read(), re.M):
            PLATFORM_DEFINES.add(m.group(1))
        for m in re.finditer(r"^\s*#undef\s+(\w+)", open(h, encoding="latin-1").read(), re.M):
            PLATFORM_DEFINES.discard(m.group(1))
    pros = a.pros or [os.path.join(a.jrt, x) for x in COMPONENTS]
    bad = 0
    for pro in pros:
        try:
            r = convert(a.jrt, pro, a.javah)
            print(f"{r['target']:26s} src={r['sources']:3d} jni={r['jni']:4d} libs={' '.join(r['libs'])}"
                  + (f"  MISSING {r['missing']}" if r["missing"] else ""))
        except Exception as e:                       # noqa: BLE001
            print(f"{pro}: FAILED {e!r}")
            bad += 1
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
