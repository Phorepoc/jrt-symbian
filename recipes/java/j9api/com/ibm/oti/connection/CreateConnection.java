// Phorepoc: compile-time stand-in for the J9 (jclcldc11_23) API that JRT calls. Signatures are inferred from
// JRT call sites (commit 1986528d); this is the contract the phoneME side must implement. Not IBM code.
// J9's Connector.open(name) loads <pkg>.<scheme>.Connection for each pkg in microedition.connection.pkgs
// (JRT: com.nokia.mj.impl.gcf.protocol) and calls setParameters2 (setParameters for older protocols).
package com.ibm.oti.connection;
public interface CreateConnection {
    void setParameters(String name, int mode, boolean timeouts) throws java.io.IOException;
    javax.microedition.io.Connection setParameters2(String name, int mode, boolean timeouts) throws java.io.IOException;
}
