// Phorepoc: compile-time stand-in for the J9 (jclcldc11_23) API that JRT calls. Signatures are inferred from
// JRT call sites (commit 1986528d); this is the contract the phoneME side must implement. Not IBM code.
package javax.microedition.io;
public interface DatagramConnection extends Connection {
    int getMaximumLength() throws java.io.IOException; int getNominalLength() throws java.io.IOException;
    void send(Datagram d) throws java.io.IOException; void receive(Datagram d) throws java.io.IOException;
    Datagram newDatagram(int s) throws java.io.IOException; Datagram newDatagram(int s, String a) throws java.io.IOException;
    Datagram newDatagram(byte[] b, int s) throws java.io.IOException; Datagram newDatagram(byte[] b, int s, String a) throws java.io.IOException;
}
