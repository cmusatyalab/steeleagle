// Command gcs is the SteelEagle ground control station. It runs as an engine
// plugin: dataflows send it frames and telemetry, which it streams to
// browsers over WebRTC, and it serves the web UI.
//
// The daemon passes the plugin's args as JSON in STEELEAGLE_PLUGIN_ARGS (see
// gcs.plugin.toml), the name of its Uriel engine in ICEORYX_SERVICE, and the
// socket the GCS calls it on, to control vehicles, in CLIENT_SOCKET.
package main

import (
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"net"
	"net/http"
	"os"
	"os/signal"
	"path"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
	"time"

	"github.com/cmusatyalab/steeleagle/gcs/internal/control"
	"github.com/cmusatyalab/steeleagle/gcs/internal/feed"
	"github.com/cmusatyalab/steeleagle/gcs/internal/rtc"
	"github.com/rs/zerolog"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

const (
	argsEnv   = "STEELEAGLE_PLUGIN_ARGS"
	engineEnv = "ICEORYX_SERVICE"
	daemonEnv = "CLIENT_SOCKET"
	// shutdownTimeout is how long requests may take to finish on shutdown.
	shutdownTimeout = 5 * time.Second
)

// args are the plugin's args.
type args struct {
	HTTPAddr     string   `json:"http_addr"`
	ICEServers   []string `json:"ice_servers"`
	WebRTCPorts  string   `json:"webrtc_ports"`
	MaxInputSize int      `json:"max_input_size"`
}

// parseArgs reads the plugin's args from JSON, defaulting the ones it leaves
// out as gcs.plugin.toml does.
func parseArgs(content string) (args, error) {
	a := args{HTTPAddr: ":8080", MaxInputSize: 4 << 20}
	if content != "" {
		if err := json.Unmarshal([]byte(content), &a); err != nil {
			return args{}, fmt.Errorf("invalid plugin args: %w", err)
		}
	}
	if a.MaxInputSize <= 0 {
		return args{}, fmt.Errorf("invalid plugin args: max_input_size must be positive, not %d", a.MaxInputSize)
	}
	return a, nil
}

// parsePorts reads a port range "min-max"; empty for any port.
func parsePorts(s string) (uint16, uint16, error) {
	if s == "" {
		return 0, 0, nil
	}
	lo, hi, ok := strings.Cut(s, "-")
	if !ok {
		return 0, 0, fmt.Errorf("invalid port range %q: want min-max", s)
	}
	min, err := strconv.ParseUint(lo, 10, 16)
	if err != nil {
		return 0, 0, fmt.Errorf("invalid port range %q: %w", s, err)
	}
	max, err := strconv.ParseUint(hi, 10, 16)
	if err != nil {
		return 0, 0, fmt.Errorf("invalid port range %q: %w", s, err)
	}
	if min == 0 || min > max {
		return 0, 0, fmt.Errorf("invalid port range %q", s)
	}
	return uint16(min), uint16(max), nil
}

func main() {
	web := flag.String("web", "web/dist", "directory of the built web UI")
	engine := flag.String("engine", os.Getenv(engineEnv), "name of the Uriel engine (default: $"+engineEnv+")")
	daemon := flag.String("daemon", os.Getenv(daemonEnv), "socket of the daemon (default: $"+daemonEnv+")")
	level := flag.String("log-level", "info", "log level")
	flag.Parse()

	log := zerolog.New(os.Stderr).With().Timestamp().Str("plugin", "gcs").Logger()
	if l, err := zerolog.ParseLevel(*level); err == nil {
		log = log.Level(l)
	} else {
		log.Fatal().Err(err).Msg("invalid log level")
	}
	if err := run(*engine, *daemon, *web, os.Getenv(argsEnv), log); err != nil {
		log.Fatal().Err(err).Msg("gcs failed")
	}
}

func run(engine, daemon, web, rawArgs string, log zerolog.Logger) error {
	if engine == "" {
		return fmt.Errorf("no engine name: set -engine or $%s", engineEnv)
	}
	a, err := parseArgs(rawArgs)
	if err != nil {
		return err
	}
	portMin, portMax, err := parsePorts(a.WebRTCPorts)
	if err != nil {
		return err
	}
	hub, err := rtc.NewHub(rtc.Options{ICEServers: a.ICEServers, PortMin: portMin, PortMax: portMax}, log)
	if err != nil {
		return err
	}
	defer hub.Close()

	var conn *grpc.ClientConn
	if daemon != "" {
		conn, err = grpc.NewClient("unix://"+daemon, grpc.WithTransportCredentials(insecure.NewCredentials()))
		if err != nil {
			return fmt.Errorf("could not connect to the daemon: %w", err)
		}
		defer conn.Close()
	} else {
		log.Warn().Msg("no daemon socket; vehicles can't be controlled")
	}
	controller := control.New(grpcConn(conn), control.DefaultTimeout, log)

	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer cancel()

	ln, err := net.Listen("tcp", a.HTTPAddr)
	if err != nil {
		return err
	}
	server := &http.Server{Handler: newHandler(hub, controller, web, log), ReadHeaderTimeout: 10 * time.Second}
	errs := make(chan error, 2)
	go func() {
		log.Info().Str("addr", ln.Addr().String()).Msg("serving web UI")
		if err := server.Serve(ln); !errors.Is(err, http.ErrServerClosed) {
			errs <- fmt.Errorf("web server failed: %w", err)
		}
	}()
	go func() {
		if err := feed.Run(ctx, engine, a.MaxInputSize, log, hub.Publish); err != nil {
			errs <- err
		}
	}()

	select {
	case <-ctx.Done():
		log.Info().Msg("shutting down")
	case err = <-errs:
	}
	cancel()
	shutdownCtx, cancelShutdown := context.WithTimeout(context.Background(), shutdownTimeout)
	defer cancelShutdown()
	if shutdownErr := server.Shutdown(shutdownCtx); shutdownErr != nil {
		log.Warn().Err(shutdownErr).Msg("could not shut down web server")
	}
	return err
}

// grpcConn returns conn as a connection interface, which is nil if conn is.
func grpcConn(conn *grpc.ClientConn) grpc.ClientConnInterface {
	if conn == nil {
		return nil
	}
	return conn
}

// newHandler serves the API, and the web UI from the directory web.
func newHandler(hub *rtc.Hub, controller *control.Controller, web string, log zerolog.Logger) http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("POST /api/webrtc/offer", hub.ServeOffer)
	mux.HandleFunc("GET /api/streams", hub.ServeStreams)
	mux.HandleFunc("POST /api/start", controller.ServeStart)
	mux.HandleFunc("POST /api/command", controller.ServeCommand)
	mux.HandleFunc("POST /api/joystick", controller.ServeJoystick)
	mux.HandleFunc("POST /api/gimbal", controller.ServeGimbal)
	mux.HandleFunc("/api/", http.NotFound)
	if _, err := os.Stat(filepath.Join(web, "index.html")); err != nil {
		log.Warn().Err(err).Str("web", web).Msg("no web UI to serve; serving only the API")
		return mux
	}
	mux.Handle("/", spaHandler(web))
	return mux
}

// spaHandler serves the files of the single page app in dir, and its
// index.html for paths that aren't files, which the app routes itself.
func spaHandler(dir string) http.Handler {
	files := http.FileServer(http.Dir(dir))
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		name := filepath.Join(dir, filepath.FromSlash(path.Clean("/"+r.URL.Path)))
		if info, err := os.Stat(name); err != nil || info.IsDir() {
			http.ServeFile(w, r, filepath.Join(dir, "index.html"))
			return
		}
		files.ServeHTTP(w, r)
	})
}
