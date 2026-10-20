package main

import (
	"context"
	"net"
	"os"
	"plugin"
	"sync"
	"sync/atomic"
	"uuid"

	"github.com/cmusatyalab/steeleagle/config"
	"github.com/cmusatyalab/steeleagle/v4/core/util"
	"github.com/cmusatyalab/steeleagle/v4/core/util/policy"
	"github.com/rs/zerolog"
	"google.golang.org/grpc"
)

type pluginInfo struct {
	obj  plugin.Plugin    // plugin object
	ln   net.Listener     // listener for plugin
	conn *grpc.ClientConn // client connection to plugin
}

type serviceInfo struct {
	db     *dataStoreService // datastore service implementation
	safety *safetyService    // safety service implementation
	upload *uploadService    // upload service implementation
}

type Vehicle struct {
	Name      string               // vehicle name
	Dir       string               // path to vehicle runtime directory (absolute)
	Config    *config.PluginConfig // driver plugin config
	Running   atomic.Bool          // whether of not the vehicle is currently running
	policy    *policy.Policy       // policy for command authorization
	daemonLn  net.Listener         // daemon listener
	driver    *pluginInfo          // driver plugin reference
	mission   *pluginInfo          // mission plugin reference
	missionMu sync.Mutex           // mutex to protect mission updates
	services  *serviceInfo         // hosted services
	server    *grpc.Server         // gRPC server
	cancel    context.CancelFunc   // cancel function for active contexts
	err       error                // error populated exactly once on a fatal error
	shutdown  chan struct{}        // shutdown channel, closed once
}

func NewVehicle(
	driver plugin.Plugin,
	driverConfig *config.PluginConfig,
	options ...VehicleOption,
) (*Vehicle, error) {
	vehicle := &Vehicle{
		Name:     uuid.New().String(),
		log:      zerolog.New(os.Stderr).With().Timestamp().Logger(),
		shutdown: make(chan struct{}, 1),
	}
	for _, option := range options {
		option(vehicle)
	}

	// Create runtime directory
	var err error
	vehicle.RunDir, err = util.GetVehicleDirByName(vehicle.Name)
	if err != nil {
		vehicle.log.Error().Err(err).Str("folder", vehicle.RunDir).
			Msg("Unable to create vehicle directory")
		return nil, err
	}
	vehicle.log.Debug().Str("folder", vehicle.RunDir).
		Msg("vehicle folder configured")

	// Policy and law setup
	// TODO: parse control law from default law in defaults/ (embed in constants.go)
	// TODO: create a new policy with that law and default rego also embeded in constants.go
	vehicle.policy = NewPolicy()

	// TODO: create gRPC server with the router in until/router. Add the following rules to it:
	// First, you need to change router to support glob matching for header/service
	// lookups. Then add the rules:
	// - all serivces/driver/ methods go to the driver conn
	// - all services/mission/ methods go to the mission conn
	//
	vehicle.services = grpc.NewServer()
}
