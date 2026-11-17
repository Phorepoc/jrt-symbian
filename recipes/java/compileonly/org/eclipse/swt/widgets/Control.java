// Phorepoc compile-only stand-in: nokialcdui TactileFeedback only tests instanceof Control and reads .handle.
// The real class is eSWT (javauis/eswt_akn, deferred); at run time the class is simply absent.
package org.eclipse.swt.widgets;
public abstract class Control { public int handle; }
