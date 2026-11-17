// Phorepoc: compile-time stand-in for the J9 (jclcldc11_23) API that JRT calls. Signatures are inferred from
// JRT call sites (commit 1986528d); this is the contract the phoneME side must implement. Not IBM code.
// The VM instantiates the class named by -Dcom.ibm.oti.nokiaextcldc...: JRT's SystemPropertyExtension
// (package com.ibm.oti.nokiaextcldc) wraps System properties in a dynamic SystemPropertyHashtable.
package com.ibm.oti.util;
public interface SystemPropertiesHook { java.util.Hashtable extendSystemProperties(java.util.Hashtable original); }
