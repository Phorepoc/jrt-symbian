// Copyright The Phorepoc Authors
// SPDX-License-Identifier: Apache-2.0
// jrtprobe -- RLibrary::Load of a JRT DLL, Lookup(1) = jni_lookup, then jni_lookup(<a JNI function the DLL defines>).
// What a VM does to bind a Java class's natives. Prints "[jrtprobe] ..." and a final PASS/FAIL line.
#include <e32base.h>
#include <e32debug.h>

typedef void (*TFunc)();
typedef TFunc (*TJniLookup)(const char*);

static TBool Probe(const TDesC& aDll, const char* aFn)
    {
    RLibrary lib;
    TInt r = lib.Load(aDll);
    if (r != KErrNone)
        {
        RDebug::Print(_L("[jrtprobe] %S: Load=%d FAIL"), &aDll, r);
        return EFalse;
        }
    TJniLookup lookup = reinterpret_cast<TJniLookup>(lib.Lookup(1));
    TFunc fn = lookup ? lookup(aFn) : NULL;
    TFunc none = lookup ? lookup("Java_no_such_Function") : NULL;
    TPtrC8 name(reinterpret_cast<const TUint8*>(aFn));
    TBuf<160> n;
    n.Copy(name.Left(160));
    RDebug::Print(_L("[jrtprobe] %S: Load=0 jni_lookup=0x%08x %S=0x%08x (unknown name -> 0x%08x)"),
                  &aDll, (TUint)lookup, &n, (TUint)fn, (TUint)none);
    TBool ok = lookup && fn && !none;
    lib.Close();
    return ok;
    }

TInt E32Main()
    {
    RDebug::Print(_L("[jrtprobe] start"));
    TBool ok = Probe(_L("javautils.dll"), "Java_com_nokia_mj_impl_properties_common_FreeMemory__1getFreeMemory");
    ok = Probe(_L("eswt.dll"), "Java_org_eclipse_ercp_swt_expanded_internal_OS_Browser_1Back") && ok;
    RDebug::Print(ok ? _L("[jrtprobe] PASS") : _L("[jrtprobe] FAIL"));
    return 0;
    }
