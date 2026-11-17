// Phorepoc: compile-time stand-in for the J9 (jclcldc11_23) API that JRT calls. Signatures are inferred from
// JRT call sites (commit 1986528d); this is the contract the phoneME side must implement. Not IBM code.
package javax.microedition.io;
public interface Datagram extends java.io.DataInput, java.io.DataOutput {
    String getAddress(); byte[] getData(); int getLength(); int getOffset(); void setAddress(String a) throws java.io.IOException;
    void setAddress(Datagram d); void setLength(int l); void setData(byte[] b, int o, int l); void reset();
}
