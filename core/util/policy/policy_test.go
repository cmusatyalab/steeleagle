package policy

import (
	"bytes"
	"context"
	"os"
	"strings"
	"sync"
	"testing"

	"github.com/cmusatyalab/steeleagle/config"
	"github.com/rs/zerolog"
)

// Paths to the default Rego policy and control law used by most tests
const regoPath string = "./testdata/check.rego"
const lawPath string = "./testdata/laws.toml"

// loadTestPolicy builds a policy from the testdata law and Rego files.
func loadTestPolicy(t *testing.T, opts ...PolicyOption) *Policy {
	t.Helper()
	law, err := config.ParseControlLawFromFilepath(lawPath)
	if err != nil {
		t.Fatalf("couldn't parse law file: %v", err)
	}
	rego, err := os.ReadFile(regoPath)
	if err != nil {
		t.Fatalf("couldn't read rego file: %v", err)
	}
	opts = append([]PolicyOption{WithLogger(zerolog.Nop())}, opts...)
	p, err := NewPolicy(*law, string(rego), opts...)
	if err != nil {
		t.Fatalf("couldn't create policy: %v", err)
	}
	return p
}

// simpleLaw returns a two state law for tests that supply their own Rego.
func simpleLaw() config.ControlLaw {
	return config.ControlLaw{
		First: "A",
		States: []config.ControlLawState{
			{Name: "A"},
			{Name: "B"},
		},
	}
}

// TestNewPolicy ensures that a policy built from a valid law starts in the
// law's first state with every state loaded.
func TestNewPolicy(t *testing.T) {
	p := loadTestPolicy(t)
	if p.currentState != "REMOTE" {
		t.Errorf("expected initial state REMOTE, got %s", p.currentState)
	}
	if len(p.lawMap) != 2 {
		t.Errorf("expected 2 states in law map, got %d", len(p.lawMap))
	}
}

// TestNewPolicyErrors ensures that malformed laws and invalid Rego are
// rejected when creating a policy.
func TestNewPolicyErrors(t *testing.T) {
	rego, err := os.ReadFile(regoPath)
	if err != nil {
		t.Fatalf("couldn't read rego file: %v", err)
	}

	tests := []struct {
		name string
		law  config.ControlLaw
		rego string
	}{
		{
			name: "unnamed state",
			law:  config.ControlLaw{First: "A", States: []config.ControlLawState{{Name: ""}}},
			rego: string(rego),
		},
		{
			name: "duplicate state",
			law:  config.ControlLaw{First: "A", States: []config.ControlLawState{{Name: "A"}, {Name: "A"}}},
			rego: string(rego),
		},
		{
			name: "invalid rego",
			law:  simpleLaw(),
			rego: "package policy\n\nthis is not rego",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			p, err := NewPolicy(tt.law, tt.rego, WithLogger(zerolog.Nop()))
			if err == nil {
				t.Errorf("expected error, got none")
			}
			if p != nil {
				t.Errorf("expected nil policy on error")
			}
		})
	}
}

// TestWithLogger ensures that a custom logger passed as an option receives
// the policy's log output.
func TestWithLogger(t *testing.T) {
	var buf bytes.Buffer
	p := loadTestPolicy(t, WithLogger(zerolog.New(&buf)))
	if _, _, err := p.SafeCheckAndTransit(context.Background(), "server/steeleagle.MissionService/StartMission"); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if buf.Len() == 0 {
		t.Errorf("expected custom logger to receive output")
	}
}

// TestSafeCheckAndTransit ensures that commands are allowed or denied
// according to the current law state, and that matching commands transit the
// policy between states.
func TestSafeCheckAndTransit(t *testing.T) {
	p := loadTestPolicy(t)
	ctx := context.Background()

	// Steps run in order since each may transition the policy state
	steps := []struct {
		name    string
		command string
		allowed bool
		state   string
	}{
		{"server allowed in REMOTE", "server/steeleagle.ControlService/TakeOff", true, "REMOTE"},
		{"mission denied in REMOTE", "mission/steeleagle.ControlService/Land", false, "REMOTE"},
		{"external denied in REMOTE", "external/steeleagle.ControlService/Land", false, "REMOTE"},
		{"mission start transits to LOCAL", "server/steeleagle.MissionService/StartMission", true, "LOCAL"},
		{"mission control allowed in LOCAL", "mission/steeleagle.ControlService/Land", true, "LOCAL"},
		{"mission data allowed in LOCAL", "mission/steeleagle.DataService/GetTelemetry", true, "LOCAL"},
		{"mission other service denied in LOCAL", "mission/steeleagle.MissionService/StopMission", false, "LOCAL"},
		{"unknown denied in LOCAL", "unknown/steeleagle.ControlService/Land", false, "LOCAL"},
		{"server control transits to REMOTE", "server/steeleagle.ControlService/Hold", true, "REMOTE"},
		{"mission denied after return to REMOTE", "mission/steeleagle.ControlService/Land", false, "REMOTE"},
		{"admin start transits to LOCAL", "admin/steeleagle.MissionService/StartMission", true, "LOCAL"},
		{"admin stop transits to REMOTE", "admin/steeleagle.MissionService/StopMission", true, "REMOTE"},
	}

	for _, s := range steps {
		allowed, state, err := p.SafeCheckAndTransit(ctx, s.command)
		if err != nil {
			t.Fatalf("%s: unexpected error: %v", s.name, err)
		}
		if allowed != s.allowed {
			t.Errorf("%s: expected allowed=%v, got %v", s.name, s.allowed, allowed)
		}
		if state != s.state {
			t.Errorf("%s: expected returned state %s, got %s", s.name, s.state, state)
		}
		if p.currentState != s.state {
			t.Errorf("%s: expected state %s, got %s", s.name, s.state, p.currentState)
		}
	}
}

// TestSafeCheckAndTransitBadState ensures that a transition to a state
// missing from the law is denied and leaves the policy in its current state.
func TestSafeCheckAndTransitBadState(t *testing.T) {
	// Rego that always tries to transit to a state not in the law
	rego := `package policy

import rego.v1

allowed := true
next_state := "MISSING"
`
	p, err := NewPolicy(simpleLaw(), rego, WithLogger(zerolog.Nop()))
	if err != nil {
		t.Fatalf("couldn't create policy: %v", err)
	}

	allowed, state, err := p.SafeCheckAndTransit(context.Background(), "server/foo.Service/Bar")
	if err == nil {
		t.Errorf("expected error transiting to missing state")
	}
	if allowed {
		t.Errorf("expected command to be denied when transit fails")
	}
	if state != "A" {
		t.Errorf("expected returned state A, got %s", state)
	}
	if p.currentState != "A" {
		t.Errorf("expected state to remain A, got %s", p.currentState)
	}
}

// TestSafeCheckAndTransitNoResults ensures that commands are denied when the
// Rego query returns no decision.
func TestSafeCheckAndTransitNoResults(t *testing.T) {
	// Package name doesn't match the data.policy query, so nothing comes back
	rego := `package other

import rego.v1

allowed := true
`
	p, err := NewPolicy(simpleLaw(), rego, WithLogger(zerolog.Nop()))
	if err != nil {
		t.Fatalf("couldn't create policy: %v", err)
	}

	allowed, state, err := p.SafeCheckAndTransit(context.Background(), "server/foo.Service/Bar")
	if err == nil {
		t.Errorf("expected error for empty rego results")
	}
	if allowed || state != "A" {
		t.Errorf("expected deny in state A, got allowed=%v state=%q", allowed, state)
	}
}

// TestSafeCheckAndTransitEvalError ensures that Rego evaluation errors are
// surfaced and the command is denied.
func TestSafeCheckAndTransitEvalError(t *testing.T) {
	// Conflicting complete rule values make evaluation fail at runtime
	rego := `package policy

import rego.v1

allowed := true if input.command
allowed := false if input.command
`
	p, err := NewPolicy(simpleLaw(), rego, WithLogger(zerolog.Nop()))
	if err != nil {
		t.Fatalf("couldn't create policy: %v", err)
	}

	allowed, _, err := p.SafeCheckAndTransit(context.Background(), "server/foo.Service/Bar")
	if err == nil {
		t.Fatalf("expected error for failed rego evaluation")
	}
	if !strings.Contains(err.Error(), "failed to evaluate rego query") {
		t.Errorf("expected evaluation error, got %v", err)
	}
	if allowed {
		t.Errorf("expected deny on evaluation error")
	}
}

// TestSafeCheckAndTransitBadDecision ensures that a Rego decision which
// can't be decoded is treated as a denial.
func TestSafeCheckAndTransitBadDecision(t *testing.T) {
	// Decision fields have the wrong types and can't be unmarshaled
	rego := `package policy

import rego.v1

allowed := "yes"
`
	p, err := NewPolicy(simpleLaw(), rego, WithLogger(zerolog.Nop()))
	if err != nil {
		t.Fatalf("couldn't create policy: %v", err)
	}

	allowed, _, err := p.SafeCheckAndTransit(context.Background(), "server/foo.Service/Bar")
	if err == nil {
		t.Errorf("expected error for malformed decision")
	}
	if allowed {
		t.Errorf("expected deny on malformed decision")
	}
}

// TestSafeCheckAndTransitConcurrent ensures that concurrent checks are safe
// and always leave the policy in a valid state.
func TestSafeCheckAndTransitConcurrent(t *testing.T) {
	p := loadTestPolicy(t)
	ctx := context.Background()

	commands := []string{
		"server/steeleagle.MissionService/StartMission",
		"server/steeleagle.ControlService/Hold",
		"mission/steeleagle.ControlService/Land",
	}

	var wg sync.WaitGroup
	for i := 0; i < 50; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			if _, _, err := p.SafeCheckAndTransit(ctx, commands[i%len(commands)]); err != nil {
				t.Errorf("unexpected error: %v", err)
			}
		}(i)
	}
	wg.Wait()

	p.mu.RLock()
	defer p.mu.RUnlock()
	if p.currentState != "REMOTE" && p.currentState != "LOCAL" {
		t.Errorf("policy ended in invalid state %s", p.currentState)
	}
}
