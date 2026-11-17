// Phorepoc: compile-time stand-in for the J9 (jclcldc11_23) API that JRT calls. Signatures are inferred from
// JRT call sites (commit 1986528d); this is the contract the phoneME side must implement. Not IBM code.
package javax.microedition.io;
public interface OutputConnection extends Connection {
    java.io.OutputStream openOutputStream() throws java.io.IOException;
    java.io.DataOutputStream openDataOutputStream() throws java.io.IOException;
}
