// Phorepoc: compile-time stand-in for the J9 (jclcldc11_23) API that JRT calls. Signatures are inferred from
// JRT call sites (commit 1986528d); this is the contract the phoneME side must implement. Not IBM code.
package javax.microedition.io;
public class Connector {
    public static final int READ = 1, WRITE = 2, READ_WRITE = 3;
    private Connector() {}
    public static Connection open(String n) throws java.io.IOException { return open(n, READ_WRITE, false); }
    public static Connection open(String n, int m) throws java.io.IOException { return open(n, m, false); }
    public static Connection open(String n, int m, boolean t) throws java.io.IOException { throw new ConnectionNotFoundException(n); }
    public static java.io.DataInputStream openDataInputStream(String n) throws java.io.IOException { return null; }
    public static java.io.DataOutputStream openDataOutputStream(String n) throws java.io.IOException { return null; }
    public static java.io.InputStream openInputStream(String n) throws java.io.IOException { return null; }
    public static java.io.OutputStream openOutputStream(String n) throws java.io.IOException { return null; }
}
