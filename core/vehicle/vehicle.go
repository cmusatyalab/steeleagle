package vehicle

import (
	"context"
	"fmt"
	"net"
	"os"
	"path/filepath"

	driver_pb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/services/driver"
	vehicle_pb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/services/vehicle"
	"github.com/cmusatyalab/steeleagle/core/util"
	"github.com/google/uuid"
	"github.com/mwitkow/grpc-proxy/proxy"
	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"
	"google.golang.org/grpc"
)

type Vehicle struct {
	id           string           // auto-generated ID for path disambiguation
	name         string           // vehicle name
	runDir       string           // path to vehicle runtime directory
	pluginConfig PluginConfig     // plugin configuration
	policyCfg    PolicyConfig     // policy configuration
	policy       policyState      // active policy state
	driver       *grpc.ClientConn // driver gRPC client connection
	mission      *grpc.ClientConn // mission gRPC client connection
	listeners    []net.Listener   // list of all active listeners
	services     *grpc.Server     // gRPC server instance
	log          zerolog.Logger   // logger object
	outFile      *os.File         // output file to log to (if no logger is provided)
	errCh        <-chan error     // error channel shared by listeners
	dataSvc      DataService      // data service
}

// Create a new vehicle with the given plugins and options.
func NewVehicle(pluginCfg PluginConfig, options ...VehicleOption) (*Vehicle, error) {
	// Set default input options and retrieve options
	vehicle := &Vehicle{
		id:           uuid.New().String(),
		name:         uuid.New().String(),
		pluginConfig: pluginCfg,
		outFile:      os.Stdout,
	}
	for _, option := range options {
		option(vehicle)
	}

	// Check if a logger is set, and if not initialize one
	if vehicle.log.GetLevel() == zerolog.Disabled {
		vehicle.log = zerolog.New(vehicle.outFile).With().Timestamp().Logger()
	}

	// Create the runtime directory
	var err error
	vehicle.runDir, err = util.GetVehicleDirByID(vehicle.name)
	if err != nil {
		vehicle.log.Error().Err(err).Str("folder", vehicle.runDir).Msg("Unable to create vehicle directory")
		return nil, err
	}
	vehicle.log.Debug().Str("folder", vehicle.runDir).Msg("vehicle folder configured")

	// Set up law handling
	vehicle.policy = getPolicy(vehicle.policyCfg)

	// Set up gRPC servers and set up auth interceptor chain
	vehicle.services = grpc.NewServer(
		grpc.StreamInterceptor(vehicle.getInterceptor()),
		grpc.CustomCodec(proxy.Codec()),
		grpc.UnknownServiceHandler(proxy.TransparentHandler(
			vehicle.getProxyDirector(),
		)),
	)

	// Register data service
	vehicle_pb.RegisterDataServiceServer(vehicle.services, &DataService{vehicle: vehicle})

	return vehicle, nil
}

func (v *Vehicle) Start(ctx context.Context) error {
	// Set up new context
	ctx, cancel := context.WithCancel(ctx)
	defer cancel()

	// Stop the gRPC server once done
	defer v.services.GracefulStop()

	// Create a main socket listener with AuthCode ExternalCode. The main
	// socket is a general endpoint for arbitrary entities to make API calls to
	// the vehicle.
	var err error
	mainSocketPath := filepath.Join(v.runDir, MainSocket)
	ln, err := createUnixSocketListener(mainSocketPath)
	if err != nil {
		return err
	}
	v.listeners = append(
		v.listeners,
		util.NewCodedListener(ln, util.ExternalCode, nil),
	)

	// Create an admin socket listener with AuthCode AdminCode. The admin
	// socket is intended for use by this process.
	adminSocketPath := filepath.Join(v.runDir, AdminSocket)
	ln, err = createUnixSocketListener(adminSocketPath)
	if err != nil {
		return err
	}
	v.listeners = append(
		v.listeners,
		util.NewCodedListener(ln, util.AdminCode, util.GetACL(nil, []int{os.Getpid()})),
	)

	// Start all plugins and register listeners
	if v.driver != nil {
		_, v.driver, err = v.pluginConfig.Driver.Start(ctx)
		if err != nil {
			v.log.Error().Err(err).Msg("could not start driver plugin, aborting")
			return err
		}
	}
	if v.pluginConfig.Mission != nil {
		ln, v.mission, err = v.pluginConfig.Mission.Start(ctx)
		if err != nil {
			v.log.Error().Err(err).Msg("could not start mission plugin, aborting")
			return err
		}
		v.listeners = append(v.listeners, ln)
	}
	for _, plugin := range v.pluginConfig.Plugins {
		ln, _, err = plugin.Start(ctx)
		if err != nil {
			if err != nil {
				return err
			}
		}
		v.listeners = append(v.listeners, ln)
	}

	// Serve the gRPC server at all listeners
	return nil
}

func (v *Vehicle) Watch() <-chan error {
	return nil
}

func (v *Vehicle) Wait() error {
	return nil
}

func (v *Vehicle) Name() string {
	return v.name
}

func (v *Vehicle) ControlState() string {
	v.policy.mu.RLock()
	defer v.policy.mu.RUnlock()
	return v.policy.currentState
}

func createUnixSocketListener(path string) (net.Listener, error) {
	os.RemoveAll(path)
	ln, err := net.Listen("unix", path)
	if err != nil {
		log.Error().Err(err).Str("file", path).Msg("could not listen on socket, aborting")
		return nil, fmt.Errorf("can't listen at file %s: %w", path, err)
	}
	return ln, nil
}

// Start video streaming with the given resolution
func (s *DataService) StartVideoStream(
	ctx context.Context,
	res driver_pb.GetVideoStreamURLRequest_Resolution) (chan error, error) {
	client := driver_pb.NewStreamServiceClient(s.vehicle.driver)
	req := &driver_pb.GetVideoStreamURLRequest{Resolution: res}

	// Send request to driver to get video stream URL
	_, err := client.GetVideoStreamURL(ctx, req)
	if err != nil {
		return nil, err
	}

	return nil, nil
}

// Start streaming telemetry from the vehicle driver. Launches a goroutine
// that performs the streaming and updates the data service as telemetry
// is received. The launched goroutine uses the returned error channel to
// report any errors. This method is non-blocking.
func (s *DataService) StartTelemetryStream(ctx context.Context) (chan error, error) {
	client := driver_pb.NewStreamServiceClient(s.vehicle.driver)
	req := &driver_pb.StreamTelemetryRequest{}

	// Send request to driver
	stream, err := client.StreamTelemetry(ctx, req)
	if err != nil {
		return nil, fmt.Errorf("failed to start stream: %w", err)
	}

	errCh := make(chan error, 1)
	// Launch goroutine to stream telemetry
	go func() {
		for {
			// check if context has ended
			if err := ctx.Err(); err != nil {
				s.vehicle.log.Err(err).Msg("telemetry stream ended")
				errCh <- err
				return
			}
			s.recvTelemetry(ctx, stream, errCh)
		}
	}()
	return errCh, nil
}
