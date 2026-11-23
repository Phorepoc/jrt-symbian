# jrt-symbian

Nokia's Java runtime for Symbian (JRT 2.1, the Avkon-era tree of the 2010 Symbian release) and eSWT, built for the
Phorepoc OS image as a layer. It brings the native side of MIDP: the start-up chain, the common libraries, LCDUI on
Avkon, RMS, the file and generic-connection protocols, security, and eSWT.

The virtual machine is **not** here. Every Java DLL carries its natives and a JNI name table (`jni_lookup`, ordinal 1),
and a VM installed from Catalogue runs them: the same image can then take either an open VM or the owner's own.

This repository does not keep a copy of JRT. The recipes fetch the exact commit in `jrt.lock` and generate the build files.

## Layout

| Path | What |
|---|---|
| `jrt.lock` | the pins: JRT (commit of the Phorepoc fork of `oss.FCL.sf.app.JRT`) and `jni.h` (SHA-256) |
| `recipes/prepare.sh` | run by the pdk before the components: `fetch.sh` + `generate.sh` (in the toolchain container) |
| `recipes/fetch.sh` | JRT at its commit into `$PHOREPOC_BUILD/jrt/oss.FCL.sf.app.JRT`, `jni.h` into `$PHOREPOC_BUILD/jrt/epoc32/include` |
| `recipes/generate.sh` | the header exports (`jrt_exports.py`) and an `.mmp` per component (`jrt_pro2mmp.py`) |
| `recipes/jrt_exports.py` | what `sbs` did with each `exports.inf` |
| `recipes/jrt_pro2mmp.py` | a small qmake stand-in: `.pro` -> `.mmp`, the JNI table (`lookup.cpp`), the javah headers from the sources |
| `recipes/jars.sh`, `recipes/build_jars.py` | **temporary**: the classes as one jar per DLL, compiled with a host JDK against `recipes/java/j9api` (compile-only stand-ins for the original VM's API) |
| `registry/components_jrt.py` | the components (and their jars, into `Z:esource\java\jvm\lib\jrt`), merged into core's registry |
| `os/src/tests/jrtprobe` | a load probe: `RLibrary::Load` + `jni_lookup` of `javautils.dll` and `eswt.dll` (`SSM_TEST=jrtprobe`) |

## Build

A board lists this repository in its `board.conf` `REPOS`; the pdk then runs `recipes/prepare.sh` and builds the
components with the rest of the image. By hand, in the toolchain container:

    PHOREPOC_BUILD=... PHOREPOC_PDK=... PHOREPOC_ARCH=x32 bash recipes/prepare.sh
    phe component build -b pc jvmnativeport javautils ...

## What the build changes, and why

JRT itself is compiled unmodified. The build differs from Nokia's in these places only:

- qmake is replaced by `jrt_pro2mmp.py`; the Qt-era defines are dropped from the generated `build_defines.*`
  (this tree is the Avkon one), and `RD_JAVA_STDCPPV5` too: the image's C++ library is Open C++ with STLport.
- `jxe.c` (the original VM's romized classes, made by a closed tool) is empty: the classes come as jars.
- The javah headers are written from the sources (the JNI functions they define, the constants from the `.java`), so the
  build needs no Java compiler.
- `jni.h` is the Android Open Source Project's (Apache-2.0) with two changes, both to match the ABI JRT's frozen `.def`
  files and eSWT expect: the C++ structs are named `JNIEnv_` / `JavaVM_`, and `jweak` is its own class.
- The tree is fetched under its package name (`oss.FCL.sf.app.JRT`), so the pdk builds it under the S60 product variant
  (`bldvariant.hrh`, with the platform's R&D flags such as `RD_SCALABLE_UI_V2` and `RD_TACTILE_FEEDBACK`), as the 2010
  build did for this app-layer package. The JNI tables honour the `#if` blocks against the same flags.
- The jars (temporary) are compiled against the JDK 8 API, not a CLDC library: files that need CLDC are left out and
  listed in `excluded.txt`. The VM's own class library replaces this step.

## Licences

JRT and eSWT: Eclipse Public License 1.0 (`LICENSES/EPL-1.0.txt`), copyright Nokia Corporation and/or its
subsidiaries, as their file headers say. `jni.h`: Apache-2.0, the Android Open Source Project. Phorepoc's recipes and
registry: Apache-2.0 (`LICENSE`). See `NOTICE`.
