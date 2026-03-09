package core

import (
    "google.golang.org/grpc/connectivity"
)

type HealthStatus struct {
    Control     connectivity.State
    Mission     connectivity.State
}

type VehicleStatus struct {
    Name        string
    Path        string
    State       string
    Health      HealthStatus
}

type BackendStatus struct {
    Path        string
}
