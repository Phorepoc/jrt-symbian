// Phorepoc: compile-time stand-in for the J9 (jclcldc11_23) API that JRT calls. Signatures are inferred from
// JRT call sites (commit 1986528d); this is the contract the phoneME side must implement. Not IBM code.
package com.ibm.oti.vm;
public final class VM {
    private VM() {}
    public static void loadLibrary(String name) { throw new UnsatisfiedLinkError(name); }   // JvmPortCldc.loadSystemLibrary
    public static void setDaemonThread(Thread t) {}                 // JvmPortCldc.setThreadAsDaemon
    public static void runFinalization() {}                         // JvmPortCldc.runFinalization
    public static void enableFinalization(Class c) {}               // JvmPortCldc, SystemPropertyExtension
    public static void localGC() {}                                 // JvmPortCommon.runYoungGenerationGc
    public static void stopExit() {}                                // disableRuntimeExit: System.exit() throws for MIDlets
    public static void allowMidpExit() {}                           // enableRuntimeExit
    public static void addRestrictedPackages(String[] p) {}         // MIDlets may not load classes there
    public static void addProtectedPackages(String[] p) {}          // MIDlets may not define classes there
    public static void appendToClassPath(String path) {}            // the MIDlet jar
    public static int contractOldSpaceFully() { return 0; }         // shrinkJavaHeapToMinimum
    public static int expandOldSpace(int amount) { return 0; }      // expandJavaHeap
    public static java.io.InputStream getResourceAsMemInputStream(String jar, String res) { return null; } // must implement OSMemoryAccessor
}
