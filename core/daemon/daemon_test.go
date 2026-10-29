package daemon

import (
	"encoding/json"
	"fmt"
	"net"
	"os"
	"slices"
	"strconv"
	"strings"
	"testing"
	"time"

	daemonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/daemon"
	"github.com/gorilla/websocket"
	"google.golang.org/grpc/codes"
)

// logdyMessage is the part of a logdy websocket message the tests read.
type logdyMessage struct {
	MessageType string `json:"message_type"`
	Messages    []struct {
		Content string `json:"content"`
	} `json:"messages"`
}

// TestLogServer checks that a daemon serves the logdy websocket, and that a
// service's log lines are streamed on it. It is the only test that runs a log
// server, since only one can run per process.
func TestLogServer(t *testing.T) {
	requirePixi(t)
	const marker = "logdy test line"
	logPort := freePort(t)
	config := testConfig(t, "solo", "", echo("talker", fmt.Sprintf("{ log = %q }", marker)))
	config = strings.Replace(config, "[daemon]\n",
		fmt.Sprintf("[daemon]\nlogs = %d\nbind = %q\n", logPort, orchAddr), 1)
	d := newTestDaemonWith(t, &testNet{addr: orchAddr, fabric: newFabric()}, config)
	d.run()

	addr := net.JoinHostPort(orchAddr.String(), strconv.Itoa(logPort))
	conn, _, err := websocket.DefaultDialer.Dial("ws://"+addr+"/ws?should_follow=true", nil)
	if err != nil {
		t.Fatalf("couldn't connect to logdy websocket: %v", err)
	}
	defer conn.Close()

	// logdy greets each client, then sends log lines in bulk
	conn.SetReadDeadline(time.Now().Add(15 * time.Second))
	var msg logdyMessage
	if err := conn.ReadJSON(&msg); err != nil {
		t.Fatalf("couldn't read from logdy websocket: %v", err)
	}
	if msg.MessageType != "client_joined" {
		t.Fatalf("got first message %q, want client_joined", msg.MessageType)
	}
	for {
		_, b, err := conn.ReadMessage()
		if err != nil {
			t.Fatalf("service log line never arrived on logdy websocket: %v", err)
		}
		if err := json.Unmarshal(b, &msg); err != nil {
			t.Fatalf("bad logdy message %s: %v", b, err)
		}
		for _, m := range msg.Messages {
			if strings.Contains(m.Content, marker) {
				return
			}
		}
	}
}

// TestRunServices checks that a daemon starts its services in the order of
// engines, vehicles and extras, each with its default or configured auth, and
// with its plugin name, args and, for engines, iceoryx service in its
// environment.
func TestRunServices(t *testing.T) {
	requirePixi(t)
	d := standalone(t,
		testService{name: "x", typ: "extra", plugin: "echo", args: `{ n = 1 }`, auth: "user"},
		testService{name: "v", typ: "vehicle", plugin: "driver"},
		testService{name: "e", typ: "engine", plugin: "detector"},
	)
	d.run()

	resp, err := d.listServices()
	if err != nil {
		t.Fatal(err)
	}
	var names, auths []string
	for _, s := range resp.GetServices() {
		names = append(names, s.GetName())
		auths = append(auths, s.GetAuth())
		if !s.GetRunning() {
			t.Errorf("service %s isn't running", s.GetName())
		}
		if s.GetUri() != testPkg {
			t.Errorf("service %s has uri %q, want %q", s.GetName(), s.GetUri(), testPkg)
		}
	}
	if want := []string{"127.0.0.1.e", "127.0.0.1.v", "127.0.0.1.x"}; !slices.Equal(names, want) {
		t.Errorf("services = %v, want %v", names, want)
	}
	if want := []string{"external", "privileged", "user"}; !slices.Equal(auths, want) {
		t.Errorf("auths = %v, want %v", auths, want)
	}
	if len(resp.GetRemotes()) != 0 {
		t.Errorf("remotes = %v, want none", resp.GetRemotes())
	}
	if resp.GetServices()[0].GetConfig() == nil {
		t.Error("engine has no plugin config")
	}

	if log := readLog(t, "127.0.0.1.x"); !strings.Contains(log, `plugin=echo.plugin.toml args={"n":1} iceoryx=`+"\n") {
		t.Errorf("extra log = %q, want its plugin and args, and no iceoryx service", log)
	}
	if log := readLog(t, "127.0.0.1.e"); !strings.Contains(log, "plugin=detector.plugin.toml args={} iceoryx=127.0.0.1.e\n") {
		t.Errorf("engine log = %q, want its plugin, empty args, and its service name as its iceoryx service", log)
	}

	if !d.connected() {
		t.Error("standalone daemon isn't connected")
	}
	if err := d.stop(); err != nil {
		t.Errorf("Run() = %v, want nil", err)
	}
	for _, name := range []string{"127.0.0.1.e", "127.0.0.1.v", "127.0.0.1.x"} {
		if running, _ := d.pluginRunning(name); running {
			t.Errorf("service %s still running after the daemon stopped", name)
		}
	}
	if _, err := os.Stat(d.socketPath); err == nil {
		t.Error("control socket left behind")
	}
}

// TestServiceFailure checks that a daemon whose service fails to start still
// starts its other services, and lists the failed one as not running, with
// the error it failed with, which a failed restart keeps.
func TestServiceFailure(t *testing.T) {
	requirePixi(t)
	d := standalone(t, echo("a", "{}"), echo("b", `{ fail = true }`), echo("c", "{}"))
	d.run()

	resp, err := d.listServices()
	if err != nil {
		t.Fatalf("ListServices() = %v, want nil", err)
	}
	errs := map[string]string{}
	for _, s := range resp.GetServices() {
		errs[s.GetName()] = s.GetError()
	}
	if got := running(resp); !got["127.0.0.1.a"] || got["127.0.0.1.b"] || !got["127.0.0.1.c"] {
		t.Errorf("running = %v, want a and c, but not b", got)
	}
	if errs["127.0.0.1.a"] != "" || errs["127.0.0.1.b"] == "" || errs["127.0.0.1.c"] != "" {
		t.Errorf("errors = %v, want only b's", errs)
	}

	// A failed restart keeps the service's error
	_, err = d.client.RestartService(callCtx(t, 5*time.Second),
		daemonpb.RestartServiceRequest_builder{ServiceNames: "127.0.0.1.b"}.Build())
	expectCode(t, err, codes.Internal, "127.0.0.1.b")
	if resp, err = d.listServices(); err != nil {
		t.Fatal(err)
	}
	for _, s := range resp.GetServices() {
		if s.GetName() == "127.0.0.1.b" && (s.GetRunning() || s.GetError() == "") {
			t.Errorf("service b after a failed restart = %v, want stopped with an error", s)
		}
	}
	if !d.connected() {
		t.Error("standalone daemon isn't connected")
	}
}

// TestServiceFailureStop checks that a daemon with a service that failed to
// start stops cleanly.
func TestServiceFailureStop(t *testing.T) {
	requirePixi(t)
	d := standalone(t, echo("b", `{ fail = true }`))
	d.run()
	if err := d.stop(); err != nil {
		t.Errorf("Run() = %v, want nil", err)
	}
}

// TestMissingPackage checks that a daemon whose services use a package that
// isn't installed keeps running without them, like one whose services fail
// to start, so that it can be reconfigured.
func TestMissingPackage(t *testing.T) {
	config := testConfig(t, "solo", "") + `
[[services]]
name = "a"
type = "extra"
[services.plugin]
plugin = "echo"
package = "example.com/not/installed"
`
	n := &testNet{addr: orchAddr, fabric: newFabric()}
	d := newTestDaemon(t, n, config)
	d.run()
	_, err := d.listServices()
	expectCode(t, err, codes.FailedPrecondition, "127.0.0.1.a")
	if err := d.stop(); err != nil {
		t.Errorf("Run() = %v, want nil", err)
	}
}

// TestRunTwice checks that a running daemon can't be run again.
func TestRunTwice(t *testing.T) {
	d := standalone(t)
	d.run()
	if err := d.Run(callCtx(t, 5*time.Second)); err == nil {
		t.Error("second Run() = nil, want error")
	}
	if err := d.stop(); err != nil {
		t.Errorf("Run() = %v, want nil", err)
	}
}
