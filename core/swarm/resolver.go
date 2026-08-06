package swarm

import "net/netip"

// VehicleResolver resolves a vehicle name to the address of its
// ControlService/MissionService gRPC server.
type VehicleResolver interface {
	Resolve(name string) (netip.AddrPort, bool)
}
