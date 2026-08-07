package swarm

// Controller consists of a Registry of connected vehicles, a RegistryServer
// for vehicles to register themselves against it, and a SwarmServer that
// dispatches commands to them by resolving names through that same Registry.
type Controller struct {
	Registry       *Registry
	RegistryServer *RegistryServer
	SwarmServer    *SwarmServer
}

// NewController wires up a Controller: a Registry, a RegistryServer serving
// it, and a SwarmServer that resolves vehicles through it.
func NewController(options ...Option) *Controller {
	registry := NewRegistry()
	return &Controller{
		Registry:       registry,
		RegistryServer: NewRegistryServer(registry),
		SwarmServer:    NewSwarmServer(registry, options...),
	}
}

// Close closes every pooled connection the SwarmServer holds to a vehicle.
func (c *Controller) Close() {
	c.SwarmServer.Close()
}
