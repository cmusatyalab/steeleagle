package swarm

import (
	"net/netip"
	"sync"
	"sync/atomic"
)

// Registry is an in-memory table mapping vehicle names to the socket address
// of their ControlService/MissionService gRPC server, built and maintained
// from live RegistryService.Register calls.
type Registry struct {
	mu      sync.RWMutex             // table mutex
	table   map[string]registryEntry // map from vehicle name to its socket address
	nextTok atomic.Uint64            // next socket token to use
}

// registryEntry represents one instance of a vehicle registration, uniquely
// identified using a session token.
type registryEntry struct {
	addr  netip.AddrPort // vehicle socket address
	token uint64         // session token
}

func NewRegistry() *Registry {
	return &Registry{
		table: make(map[string]registryEntry),
	}
}

// Register records addr as the current socket address for the named vehicle,
// returning an unregister function that removes the entry. unregister only
// removes the entry if it still matches this call's registration, so a stale
// unregister from a superseded call can't clobber a newer registration for the
// same name.
func (r *Registry) Register(name string, addr netip.AddrPort) (unregister func()) {
	token := r.nextTok.Add(1)

	r.mu.Lock()
	r.table[name] = registryEntry{addr: addr, token: token}
	r.mu.Unlock()

	return func() {
		r.mu.Lock()
		defer r.mu.Unlock()
		if cur, ok := r.table[name]; ok && cur.token == token {
			delete(r.table, name)
		}
	}
}

// Resolve returns the currently registered address for the named vehicle, if
// any.
func (r *Registry) Resolve(name string) (netip.AddrPort, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	e, ok := r.table[name]
	return e.addr, ok
}
