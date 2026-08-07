package swarm_test

import (
	"net/netip"
	"testing"

	"github.com/cmusatyalab/steeleagle/core/swarm"
)

func mustAddr(t *testing.T, s string) netip.AddrPort {
	t.Helper()
	addr, err := netip.ParseAddrPort(s)
	if err != nil {
		t.Fatalf("parsing %q: %v", s, err)
	}
	return addr
}

func TestRegistry_ResolveUnknown(t *testing.T) {
	r := swarm.NewRegistry()
	if _, ok := r.Resolve("harpy"); ok {
		t.Error("Resolve on empty registry returned ok=true, want false")
	}
}

func TestRegistry_RegisterResolve(t *testing.T) {
	r := swarm.NewRegistry()
	addr := mustAddr(t, "127.0.0.1:9000")

	unregister := r.Register("harpy", addr)
	defer unregister()

	got, ok := r.Resolve("harpy")
	if !ok {
		t.Fatal("Resolve after Register returned ok=false")
	}
	if got != addr {
		t.Errorf("Resolve = %v, want %v", got, addr)
	}
}

func TestRegistry_Unregister(t *testing.T) {
	r := swarm.NewRegistry()
	unregister := r.Register("harpy", mustAddr(t, "127.0.0.1:9000"))

	unregister()

	if _, ok := r.Resolve("harpy"); ok {
		t.Error("Resolve after unregister returned ok=true, want false")
	}
}

// TestRegistry_StaleUnregisterDoesNotClobberNewer covers the token-based guard
// in Registry.Register's returned unregister func: if a vehicle reconnects
// before the old connection's Register stream has actually torn down, the old
// stream's eventual unregister call must not evict the new, live registration.
func TestRegistry_StaleUnregisterDoesNotClobberNewer(t *testing.T) {
	r := swarm.NewRegistry()

	oldAddr := mustAddr(t, "127.0.0.1:9000")
	unregisterOld := r.Register("harpy", oldAddr)

	newAddr := mustAddr(t, "127.0.0.1:9001")
	unregisterNew := r.Register("harpy", newAddr)
	defer unregisterNew()

	// The stale call: the old connection finally notices it's done and
	// unregisters, after a newer registration has already superseded it.
	unregisterOld()

	got, ok := r.Resolve("harpy")
	if !ok {
		t.Fatal("Resolve after stale unregister returned ok=false, want the newer registration to survive")
	}
	if got != newAddr {
		t.Errorf("Resolve = %v, want the newer address %v (stale unregister clobbered it)", got, newAddr)
	}
}

func TestRegistry_IndependentVehicles(t *testing.T) {
	r := swarm.NewRegistry()
	addrA := mustAddr(t, "127.0.0.1:9000")
	addrB := mustAddr(t, "127.0.0.1:9001")

	unregisterA := r.Register("harpy", addrA)
	defer unregisterA()
	unregisterB := r.Register("ghost", addrB)

	unregisterB()

	if _, ok := r.Resolve("ghost"); ok {
		t.Error("ghost still resolvable after its own unregister")
	}
	if got, ok := r.Resolve("harpy"); !ok || got != addrA {
		t.Errorf("harpy = (%v, %v), want (%v, true) -- unrelated unregister affected it", got, ok, addrA)
	}
}
