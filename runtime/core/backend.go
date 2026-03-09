package core

import (
    "sync"

    "google.golang.org/grpc"
)

type ConnectedVehicle struct {
    // Public
    Name            string
    Hostname        string
    // Private
    services        map[string]*grpc.ClientConn
}

type Backend struct {
    path            string
    mu              sync.RWMutex
    vehicles        map[string]ConnectedVehicle
    useDataplane    bool
}

func NewBackend() (*Backend, error) {
    return nil, nil
}

func (i *Backend) run() {

}

func (i *Backend) Stop() {

}
