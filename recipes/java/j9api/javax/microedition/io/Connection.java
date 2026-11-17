// Phorepoc: compile-time stand-in for the J9 (jclcldc11_23) API that JRT calls. Signatures are inferred from
// JRT call sites (commit 1986528d); this is the contract the phoneME side must implement. Not IBM code.
// javax.microedition.io (GCF) is CLDC 1.1 core: shipped in jclcldc11_23, so the replacement class library provides it.
package javax.microedition.io;
public interface Connection { void close() throws java.io.IOException; }
