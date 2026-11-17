# Copyright The Phorepoc Authors
# SPDX-License-Identifier: Apache-2.0

r"""components_jrt -- this layer's components: Nokia's Java runtime (JRT, the Avkon-era tree pinned in jrt.lock) and
eSWT, merged into core's registry when this repository is built (PHOREPOC_ADAPTATIONS=...:<jrt-symbian>, see the pdk's
tools/emitter/paths.py).

The JRT source is not in this repository: recipes/prepare.sh fetches it at its pinned commit to $PHOREPOC_BUILD/jrt/oss.FCL.sf.app.JRT
and writes the .mmp files qmake would have written next to each .pro (recipes/jrt_pro2mmp.py), so every `mmp` below is
in the build tree. eSWT's API facade and physics have real .mmp files in the tree and are built from those.

The virtual machine is not here. The DLLs carry the natives and the JNI name tables (`jni_lookup`, ordinal 1); a VM
that runs them comes from Catalogue."""
import os

from paths import BUILD, OS_ROOT, SYMBIAN

JRT = os.path.join(BUILD, "jrt/oss.FCL.sf.app.JRT")


def _gen(rel: str, target: str) -> str:
    """The generated mmp of a .pro component: <pro dir>/<target>.mmp."""
    return os.path.join(JRT, rel, target + ".mmp")


COMPONENTS = {
    # the VM's port layer and the start-up chain (starter -> starter utils -> the VM's j9main)
    "jvmnativeport": dict(mmp=_gen("javacommons/jvms/nativeportlayer/build", "jvmnativeport")),
    "javastarter": dict(mmp=_gen("javaruntimes/standalone/build", "javastarter")),
    "javaruntimestarterutils": dict(mmp=_gen("javaruntimes/starterutils/build", "javaruntimestarterutils")),
    "javajvmargsmodifier": dict(mmp=_gen("javaruntimes/jvmargmodifier/default/build", "javajvmargsmodifier")),
    "javamidpstarter": dict(mmp=_gen("javaruntimes/midp/runtimestarter/build", "javamidpstarter")),
    "javamidpruntime": dict(mmp=_gen("javaruntimes/midp/runtime/build", "javamidpruntime")),
    # common libraries
    "javautils": dict(mmp=_gen("javacommons/utils/build", "javautils")),
    "javaenv": dict(mmp=_gen("javacommons/javaenv/build", "javaenv")),
    "javastorage": dict(mmp=_gen("javacommons/javastorage/build", "javastorage")),
    "javacomms": dict(mmp=_gen("javacommons/comms/build", "javacomms")),
    "javaipc": dict(mmp=_gen("javacommons/comms/ipclib/clientserver/build", "javaipc")),
    "javafileutils": dict(mmp=_gen("javacommons/fileutils/build", "javafileutils")),
    "javasecurity": dict(mmp=_gen("javacommons/security/build", "javasecurity")),
    "javagcf": dict(mmp=_gen("javacommons/gcfbase/build", "javagcf")),
    "javaconnectionmanager": dict(mmp=_gen("javacommons/connectionmanager/build", "javaconnectionmanager")),
    "javafile": dict(mmp=_gen("javacommons/gcfprotocols/file/build", "javafile")),
    "javarms": dict(mmp=_gen("javaextensions/midprms_db/build", "javarms")),
    # UI: LCDUI on Avkon, the core and runtime UI, eSWT
    "javalegacyutils": dict(mmp=_gen("javauis/javalegacyutils/build", "javalegacyutils")),
    "javacoreui": dict(mmp=_gen("javauis/coreui_akn/build", "javacoreui")),
    "javaruntimeui": dict(mmp=_gen("javauis/runtimeui_akn/build", "javaruntimeui")),
    "javalcdui": dict(mmp=_gen("javauis/lcdui_akn/javalcdui/build", "javalcdui")),
    "eswt": dict(mmp=_gen("javauis/eswt_akn/org.eclipse.ercp.swt.s60/native/build", "eswt")),
    "eswtdirectcontent": dict(mmp=_gen("javauis/eswt_akn/eswtdirectcontent/build", "eswtdirectcontent")),
    # media keys for eSWT (eswtapifacade: CJavaRemConManager)
    "javaremconobserver": dict(mmp=_gen("javauis/remconobserver_akn/build", "javaremconobserver")),
    "eswtapifacade": dict(mmp=os.path.join(JRT, "javauis/eswt_akn/eswtapifacade/group/eswtapifacade.mmp")),
    "eswtphysics": dict(mmp=os.path.join(JRT, "javauis/eswt_akn/eswtphysics/group/eswtphysics.mmp")),
}

# JRT's C++ throws and catches (java::util::ExceptionBase, std::exception) and uses typeid: every DLL is built with
# exceptions (eh: its frames registered with the process's unwinder) and RTTI, as Nokia's GCCE/RVCT build did.
for _c in COMPONENTS.values():
    _c.update(eh=True, cxx_eh=True)
    # headers the release carries only in its API reference export tree (elements/cftransportmacro.h ...), searched
    # last, as core does for its own components (components.API_REF_LAST)
    _c["x32_flags"] = ["-idirafter", os.path.join(SYMBIAN, "symbian-2010/oss.API_REF.Public_API/epoc32/include")]

# eswtdirectcontent includes the Avkon-era MMAPI's direct-content interfaces
COMPONENTS["eswtdirectcontent"]["x32_flags"] = COMPONENTS["eswtdirectcontent"]["x32_flags"] + [
    "-I", os.path.join(JRT, "javauis/mmapi_akn/baseline/inc")]

# The classes, one jar per DLL (recipes/jars.sh, TEMPORARY until P2): Z:\resource\java\jvm\lib\jrt\<dll>.jar, where the
# original build kept the class-container manifests (.odc). Only the jars a build made (no JDK, no jars).
JARS = os.path.join(BUILD, "jrt/jars")
for _k, _c in COMPONENTS.items():
    for _jar in [_k] + (["jrt-misc"] if _k == "javautils" else []):
        if os.path.isfile(os.path.join(JARS, _jar + ".jar")):
            _c.setdefault("rom_data", []).append(f"resource\java\jvm\lib\jrt\{_jar}.jar=.jrt/jars/{_jar}.jar")

# the load probe (a ROM built with SSM_TEST=jrtprobe starts it): RLibrary::Load + jni_lookup of javautils.dll and eswt.dll
COMPONENTS["jrtprobe"] = dict(mmp=os.path.join(OS_ROOT, "src/tests/jrtprobe/jrtprobe.mmp"), test=True)
