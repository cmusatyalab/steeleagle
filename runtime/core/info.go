package core

type VehicleState struct {
    Name string
    // Network
    Hostname string
    UseVpn bool
    // Policy
    Laws []byte
    CurrentState string
    Services map[string]bool
}
