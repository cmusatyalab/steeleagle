// Command gabrielmock is a standalone Gabriel gRPC client that mimics the
// two input producers a real vehicle driver feeds (telemetry and video
// frames), without needing a running Vehicle, driver plugin, or mission
// plugin. It exists to reproduce and debug delivery-timing issues between a
// Gabriel client and the engines it targets (e.g. the telemetry engine) in
// isolation from the rest of the SteelEagle pipeline.
package main

import (
	"context"
	"flag"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	gabrielclient "github.com/cmusatyalab/gabriel/go-client"
	gabrielpb "github.com/cmusatyalab/gabriel/protocol/go"
	commonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/common"
	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"
	"google.golang.org/grpc"
	"google.golang.org/grpc/keepalive"
)

func splitEngines(s string) []string {
	var engines []string
	for _, e := range strings.Split(s, ",") {
		if e = strings.TrimSpace(e); e != "" {
			engines = append(engines, e)
		}
	}
	return engines
}

// shutdownGracePeriod bounds how long graceful shutdown is given after ctx
// is canceled before the process is force-exited. See
// forceExitOnStuckShutdown for why this is necessary.
const shutdownGracePeriod = 5 * time.Second

// defaultKeepaliveTime overrides the vendored gabrielclient library's own
// default (10s, with PermitWithoutStream: true). That default pings far
// more often than a stock gRPC-go server's enforcement policy allows
// (internal/transport/defaults.go: defaultKeepalivePolicyMinTime = 5m,
// PermitWithoutStream: false by default) once the long-lived ClientSession
// stream is open, so the server GOAWAYs the connection with
// ENHANCE_YOUR_CALM/"too_many_pings" every few ping intervals. Since the
// producers keep real application traffic flowing continuously anyway,
// pinging this conservatively still detects a dead connection promptly
// enough in practice.
const defaultKeepaliveTime = 6 * time.Minute

func main() {
	server := flag.String("server", "localhost:9099", "Gabriel server gRPC client-facing endpoint (engines connect on a separate port, e.g. 5555)")
	vehicleID := flag.String("vehicle-id", "gabrielmock", "vehicle ID to register with the server")
	model := flag.String("model", "mock", "vehicle model to register with the server")
	telemetryEngines := flag.String("telemetry-engines", "telemetry", "comma-separated target engines for the telemetry producer")
	frameEngines := flag.String("frame-engines", "telemetry", "comma-separated target engines for the frame producer")
	telemetryHz := flag.Float64("telemetry-hz", 5, "telemetry send rate in Hz")
	frameHz := flag.Float64("frame-hz", 10, "frame send rate in Hz")
	frameWidth := flag.Int("frame-width", 1280, "synthetic frame width in pixels")
	frameHeight := flag.Int("frame-height", 720, "synthetic frame height in pixels")
	duration := flag.Duration("duration", 0, "how long to run before exiting; 0 runs until interrupted")
	keepaliveTime := flag.Duration("keepalive-time", defaultKeepaliveTime, "gRPC keepalive ping interval; must exceed the server's minimum ping interval or it will GOAWAY the connection with ENHANCE_YOUR_CALM")
	keepaliveTimeout := flag.Duration("keepalive-timeout", 20*time.Second, "time to wait for a keepalive ping ack before considering the connection dead")
	logLevel := flag.String("log-level", "info", "log level: trace, debug, info, warn, error, fatal, panic, or disabled")
	flag.Parse()

	level, err := zerolog.ParseLevel(*logLevel)
	if err != nil {
		log.Fatal().Err(err).Str("log_level", *logLevel).Msg("invalid log level")
	}
	zerolog.SetGlobalLevel(level)

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	if *duration > 0 {
		var cancel context.CancelFunc
		ctx, cancel = context.WithTimeout(ctx, *duration)
		defer cancel()
	}

	telStats := &producerStats{name: "telemetry"}
	frameStats := &producerStats{name: "frames"}
	received := &receivedStats{}
	startedAt := time.Now()

	go forceExitOnStuckShutdown(ctx, startedAt, received, telStats, frameStats)

	telProducer := newTelemetryProducer(splitEngines(*telemetryEngines), *telemetryHz, telStats)
	frameProducer := newFrameProducer(splitEngines(*frameEngines), *frameHz, *vehicleID, *frameWidth, *frameHeight, frameStats)

	consumer := func(res *gabrielpb.Result) {
		received.record(res.GetTargetEngineId())
		log.Info().
			Str("engine_id", res.GetTargetEngineId()).
			Int64("frame_id", res.GetFrameId()).
			Msg("received result")
	}

	client, err := gabrielclient.NewGrpcClient(
		*server,
		[]*gabrielclient.InputProducer{telProducer, frameProducer},
		consumer,
		gabrielclient.WithClientInfo(commonpb.VehicleInfo_builder{
			VehicleId: *vehicleID,
			Model:     *model,
		}.Build()),
		gabrielclient.WithDialOptions(grpc.WithKeepaliveParams(keepalive.ClientParameters{
			Time:                *keepaliveTime,
			Timeout:             *keepaliveTimeout,
			PermitWithoutStream: false,
		})))
	if err != nil {
		log.Fatal().Err(err).Msg("failed to create Gabriel client")
	}

	log.Info().
		Str("server", *server).
		Float64("telemetry_hz", *telemetryHz).
		Float64("frame_hz", *frameHz).
		Dur("keepalive_time", *keepaliveTime).
		Msg("starting gabriel mock client")

	errCh, err := client.Launch(ctx)
	if err != nil {
		log.Fatal().Err(err).Msg("failed to launch Gabriel client")
	}

	for err := range errCh {
		log.Error().Err(err).Msg("gabriel client error")
	}
	log.Info().Msg("gabriel mock client stopped")
	printStats(startedAt, received, telStats, frameStats)
}

// hzToInterval converts a send rate in Hz to a time.Duration tick interval.
func hzToInterval(hz float64) time.Duration {
	if hz <= 0 {
		hz = 1
	}
	return time.Duration(float64(time.Second) / hz)
}

// forceExitOnStuckShutdown works around a hang in the vendored
// gabrielclient library: if the server never acknowledges registration
// (wrong endpoint, unresponsive server), its producer goroutines block
// forever in a sync.Cond.Wait() that only a successful registration can
// wake, so canceling ctx alone cannot unblock them. Since this tool exists
// specifically to probe a possibly-misbehaving server, it must still be
// interruptible in that situation, so force the process to exit if
// graceful shutdown doesn't finish within shutdownGracePeriod. It prints
// the run's stats itself before exiting, since main's own printStats call
// is never reached on this path.
func forceExitOnStuckShutdown(
	ctx context.Context,
	startedAt time.Time,
	received *receivedStats,
	producers ...*producerStats) {
	<-ctx.Done()
	log.Warn().Dur("grace_period", shutdownGracePeriod).Msg("shutting down; forcing exit if this hangs")
	time.Sleep(shutdownGracePeriod)
	log.Warn().Msg("graceful shutdown did not complete in time; forcing exit")
	printStats(startedAt, received, producers...)
	os.Exit(1)
}
