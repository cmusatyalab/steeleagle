package main

import (
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"slices"
	"strings"
	"testing"

	"github.com/cmusatyalab/steeleagle/gcs/internal/control"
	"github.com/cmusatyalab/steeleagle/gcs/internal/rtc"
	"github.com/rs/zerolog"
)

func TestParseArgs(t *testing.T) {
	a, err := parseArgs("")
	if err != nil {
		t.Fatal(err)
	}
	if a.HTTPAddr != ":8080" || a.MaxInputSize != 4<<20 || a.ICEServers != nil || a.WebRTCPorts != "" {
		t.Errorf("parseArgs(\"\") = %+v, want the defaults of gcs.plugin.toml", a)
	}
	// The daemon passes only the args the config sets
	a, err = parseArgs(`{"http_addr": ":9000", "ice_servers": ["stun:example.com"]}`)
	if err != nil {
		t.Fatal(err)
	}
	if a.HTTPAddr != ":9000" || !slices.Equal(a.ICEServers, []string{"stun:example.com"}) || a.MaxInputSize != 4<<20 {
		t.Errorf("parseArgs() = %+v, want the set args over the defaults", a)
	}
	for _, invalid := range []string{`{`, `{"max_input_size": 0}`, `{"max_input_size": "big"}`} {
		if _, err := parseArgs(invalid); err == nil {
			t.Errorf("parseArgs(%s) succeeded, want an error", invalid)
		}
	}
}

func TestParsePorts(t *testing.T) {
	if lo, hi, err := parsePorts(""); err != nil || lo != 0 || hi != 0 {
		t.Errorf("parsePorts(\"\") = %d, %d, %v, want any port", lo, hi, err)
	}
	if lo, hi, err := parsePorts("50000-50100"); err != nil || lo != 50000 || hi != 50100 {
		t.Errorf("parsePorts() = %d, %d, %v, want 50000-50100", lo, hi, err)
	}
	for _, invalid := range []string{"50000", "a-b", "0-10", "200-100", "1-70000"} {
		if _, _, err := parsePorts(invalid); err == nil {
			t.Errorf("parsePorts(%q) succeeded, want an error", invalid)
		}
	}
}

// TestHandler ensures that the web UI's files are served, with its
// index.html for the paths it routes, and that unknown API paths aren't.
func TestHandler(t *testing.T) {
	web := t.TempDir()
	os.WriteFile(filepath.Join(web, "index.html"), []byte("index"), 0o644)
	os.Mkdir(filepath.Join(web, "assets"), 0o755)
	os.WriteFile(filepath.Join(web, "assets", "app.js"), []byte("app"), 0o644)
	hub, err := rtc.NewHub(rtc.Options{}, zerolog.Nop())
	if err != nil {
		t.Fatal(err)
	}
	defer hub.Close()
	server := httptest.NewServer(newHandler(hub, control.New(nil, control.DefaultTimeout, zerolog.Nop()), web, zerolog.Nop()))
	defer server.Close()

	for path, want := range map[string]string{
		"/":                 "index",
		"/assets/app.js":    "app",
		"/vehicles/drone1":  "index",
		"/assets":           "index",
		"/../../etc/passwd": "index",
		"/api/streams":      "[]\n",
	} {
		resp, err := http.Get(server.URL + path)
		if err != nil {
			t.Fatal(err)
		}
		body, _ := io.ReadAll(resp.Body)
		resp.Body.Close()
		if resp.StatusCode != http.StatusOK || string(body) != want {
			t.Errorf("GET %s = %d %q, want %q", path, resp.StatusCode, body, want)
		}
	}
	// Control endpoints are served, and say when there's no daemon
	resp, err := http.Post(server.URL+"/api/command", "application/json", strings.NewReader(`{"land": true, "vehicles": ["a"]}`))
	if err != nil {
		t.Fatal(err)
	}
	resp.Body.Close()
	if resp.StatusCode != http.StatusServiceUnavailable {
		t.Errorf("POST /api/command = %d, want %d", resp.StatusCode, http.StatusServiceUnavailable)
	}
	resp, err = http.Get(server.URL + "/api/missing")
	if err != nil {
		t.Fatal(err)
	}
	resp.Body.Close()
	if resp.StatusCode != http.StatusNotFound {
		t.Errorf("GET /api/missing = %d, want %d", resp.StatusCode, http.StatusNotFound)
	}
}

// TestHandlerWithoutWeb ensures that the API is still served without a
// built web UI.
func TestHandlerWithoutWeb(t *testing.T) {
	hub, err := rtc.NewHub(rtc.Options{}, zerolog.Nop())
	if err != nil {
		t.Fatal(err)
	}
	defer hub.Close()
	server := httptest.NewServer(newHandler(hub, control.New(nil, control.DefaultTimeout, zerolog.Nop()), filepath.Join(t.TempDir(), "missing"), zerolog.Nop()))
	defer server.Close()
	resp, err := http.Get(server.URL + "/api/streams")
	if err != nil {
		t.Fatal(err)
	}
	resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		t.Errorf("GET /api/streams = %d, want %d", resp.StatusCode, http.StatusOK)
	}
}
