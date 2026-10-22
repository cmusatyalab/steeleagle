package daemon

import (
	"context"
	"crypto/x509"
	"encoding/pem"
	"net/netip"
	"os"
	"path/filepath"
	"testing"

	"github.com/adrg/xdg"
	daemonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/daemon"
	"github.com/cmusatyalab/steeleagle/config"
	"github.com/cmusatyalab/steeleagle/v4/core/util/policy"
	"github.com/cmusatyalab/steeleagle/v4/core/util/router"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/connectivity"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"
)

// newTestOrchestrator returns a daemon with a temporary data directory, ready
// to be registered with.
func newTestOrchestrator(t *testing.T) *Daemon {
	t.Helper()
	t.Setenv("XDG_DATA_HOME", t.TempDir())
	xdg.Reload()
	t.Cleanup(xdg.Reload)
	d := &Daemon{
		Config: &config.DaemonConfig{Daemon: config.DaemonRoot{Port: 9000, Lcs: 9001, Hostname: "homebase"}},
		router: router.NewRouter(nil, nil, router.WithLogger(testLogger())),
		log:    testLogger(),
	}
	t.Cleanup(d.closeRemotes)
	return d
}

// callerContext returns a context for a call from ip, with the caller address
// recorded by the relay.
func callerContext(ip string) context.Context {
	return metadata.NewIncomingContext(context.Background(), metadata.Pairs(callerHeader, ip+":41234"))
}

// TestLcsCert ensures that a cert is generated for the Uriel server name and
// saved with its key, that the saved cert is reused, and that an invalid cert,
// or one for another name, is replaced.
func TestLcsCert(t *testing.T) {
	d := newTestOrchestrator(t)
	first, err := d.lcsCert()
	if err != nil {
		t.Fatalf("generate failed: %v", err)
	}
	block, _ := pem.Decode([]byte(first))
	if block == nil || block.Type != "CERTIFICATE" {
		t.Fatalf("expected a PEM cert and nothing else, got %q", first)
	}
	cert, err := x509.ParseCertificate(block.Bytes)
	if err != nil || cert.VerifyHostname(lcsServerName) != nil {
		t.Errorf("expected a cert for uriel, got %v, %v", cert, err)
	}
	dir := filepath.Join(xdg.DataHome, "steeleagle", LcsIdentityDirName)
	if info, err := os.Stat(filepath.Join(dir, LcsKeyFileName)); err != nil || info.Mode().Perm() != 0600 {
		t.Errorf("expected key saved with mode 0600, got %v, %v", info, err)
	}

	if again, err := d.lcsCert(); err != nil || again != first {
		t.Errorf("expected saved cert reused, got %v", err)
	}
	if err := os.WriteFile(filepath.Join(dir, LcsCertFileName), []byte("garbage"), 0644); err != nil {
		t.Fatal(err)
	}
	replaced, err := d.lcsCert()
	if err != nil || replaced == first {
		t.Errorf("expected invalid cert replaced, got %v", err)
	}

	// A cert for the name Gabriel clients connected with is replaced
	old, _, err := generateCert("gabriel")
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, LcsCertFileName), old, 0644); err != nil {
		t.Fatal(err)
	}
	if renamed, err := d.lcsCert(); err != nil || renamed == replaced {
		t.Errorf("expected cert for another name replaced, got %v", err)
	}
}

// TestRegisterOrchestrator ensures that a daemon registering its vehicles gets
// the local compute cert and port back, sharing one connection to it that is
// replaced when it registers on another port, and that vehicles that aren't on
// the calling daemon are rejected.
func TestRegisterOrchestrator(t *testing.T) {
	d := newTestOrchestrator(t)
	ctx := callerContext("100.64.0.7")
	req := daemonpb.RegisterOrchestratorRequest_builder{
		Vehicles: []string{"100.64.0.7/harpy", "100.64.0.7/kestrel"},
		Port:     9100,
	}.Build()
	resp, err := d.RegisterOrchestrator(ctx, req)
	if err != nil {
		t.Fatalf("register failed: %v", err)
	}
	if resp.GetPort() != 9001 || resp.GetCert() == "" {
		t.Errorf("expected cert and lcs port 9001, got %v", resp)
	}
	// Registering again reuses the connection to the daemon
	if _, err := d.RegisterOrchestrator(ctx, req); err != nil {
		t.Fatalf("second register failed: %v", err)
	}
	ip := netip.MustParseAddr("100.64.0.7")
	first, ok := d.remotes[ip]
	if !ok || len(d.remotes) != 1 || first.Target() != "passthrough:///100.64.0.7:9100" {
		t.Errorf("expected one connection to 100.64.0.7:9100, got %v", d.remotes)
	}
	// Registering on another port replaces the connection to the daemon
	moved := daemonpb.RegisterOrchestratorRequest_builder{Vehicles: req.GetVehicles(), Port: 9200}.Build()
	if _, err := d.RegisterOrchestrator(ctx, moved); err != nil {
		t.Fatalf("register on new port failed: %v", err)
	}
	if conn := d.remotes[ip]; len(d.remotes) != 1 || conn.Target() != "passthrough:///100.64.0.7:9200" {
		t.Errorf("expected the connection replaced by one to 100.64.0.7:9200, got %v", d.remotes)
	}
	if first.GetState() != connectivity.Shutdown {
		t.Errorf("expected the old connection closed, got %v", first.GetState())
	}

	bad := map[string]struct {
		vehicle string
		code    codes.Code
	}{
		"other daemon": {"100.64.0.8/harpy", codes.PermissionDenied},
		"no ip":        {"harpy", codes.InvalidArgument},
		"no name":      {"100.64.0.7/", codes.InvalidArgument},
		"bad ip":       {"homebase/harpy", codes.PermissionDenied},
	}
	noPort := daemonpb.RegisterOrchestratorRequest_builder{Vehicles: []string{"100.64.0.7/harpy"}}.Build()
	if _, err := d.RegisterOrchestrator(ctx, noPort); status.Code(err) != codes.InvalidArgument {
		t.Errorf("no port: expected InvalidArgument, got %v", err)
	}
	for name, tt := range bad {
		req := daemonpb.RegisterOrchestratorRequest_builder{Vehicles: []string{tt.vehicle}, Port: 9100}.Build()
		if _, err := d.RegisterOrchestrator(ctx, req); status.Code(err) != tt.code {
			t.Errorf("%s: expected %v, got %v", name, tt.code, err)
		}
	}
}

// TestRegisterOrchestratorLaw ensures that the daemon law lets remote daemons,
// which call with ExternalCode, register while the daemon is online.
func TestRegisterOrchestratorLaw(t *testing.T) {
	law, err := config.ParseControlLawFromBytes(DefaultLaw)
	if err != nil {
		t.Fatal(err)
	}
	p, err := policy.NewPolicy(law, policy.WithLogger(testLogger()))
	if err != nil {
		t.Fatal(err)
	}
	command := "external/" + daemonpb.DaemonService_RegisterOrchestrator_FullMethodName[1:]
	if allowed, _, err := p.SafeCheckAndTransit(context.Background(), command); err != nil || !allowed {
		t.Errorf("expected %s allowed, got %v, %v", command, allowed, err)
	}
}
