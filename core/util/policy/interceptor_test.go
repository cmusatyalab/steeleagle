package policy

import (
	"context"
	"errors"
	"net"
	"testing"

	"github.com/cmusatyalab/steeleagle/v4/core/util/listener"
	"github.com/rs/zerolog"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/peer"
	"google.golang.org/grpc/status"
)

// fakeStream is a minimal grpc.ServerStream that only supplies a context.
type fakeStream struct {
	grpc.ServerStream
	ctx context.Context
}

// Context returns the context supplied to the fake stream.
func (s *fakeStream) Context() context.Context {
	return s.ctx
}

// codedContext returns a context with a peer address tagged with code.
func codedContext(code listener.AuthCode) context.Context {
	addr := &listener.Addr{
		Addr: &net.TCPAddr{IP: net.IPv4(127, 0, 0, 1), Port: 1234},
		Code: code,
	}
	return peer.NewContext(context.Background(), &peer.Peer{Addr: addr})
}

// TestQualifyCommand ensures that commands are prefixed with the AuthCode of
// the calling peer, falling back to unknown when no code is available.
func TestQualifyCommand(t *testing.T) {
	const method = "/steeleagle.ControlService/TakeOff"

	tests := []struct {
		name     string
		ctx      context.Context
		expected string
	}{
		{"server code", codedContext(listener.ServerCode), "server" + method},
		{"admin code", codedContext(listener.AdminCode), "admin" + method},
		{"mission code", codedContext(listener.MissionCode), "mission" + method},
		{"external code", codedContext(listener.ExternalCode), "external" + method},
		{"no peer", context.Background(), "unknown" + method},
		{
			"non-coded addr",
			peer.NewContext(context.Background(), &peer.Peer{Addr: &net.TCPAddr{IP: net.IPv4(127, 0, 0, 1)}}),
			"unknown" + method,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := qualifyCommand(tt.ctx, method); got != tt.expected {
				t.Errorf("expected %s, got %s", tt.expected, got)
			}
		})
	}
}

// TestPolicyInterceptor ensures that the interceptor only forwards permitted
// commands to the handler, and transits the policy as commands are approved.
func TestPolicyInterceptor(t *testing.T) {
	p := loadTestPolicy(t)
	interceptor := p.NewStreamPolicyInterceptor()

	// Steps run in order since each may transition the policy state
	steps := []struct {
		name   string
		code   listener.AuthCode
		method string
		called bool
		status codes.Code
		state  string
	}{
		{"server allowed", listener.ServerCode, "/steeleagle.ControlService/TakeOff", true, codes.OK, "REMOTE"},
		{"mission denied in REMOTE", listener.MissionCode, "/steeleagle.ControlService/Land", false, codes.PermissionDenied, "REMOTE"},
		{"start mission transits", listener.ServerCode, "/steeleagle.MissionService/StartMission", true, codes.OK, "LOCAL"},
		{"mission allowed in LOCAL", listener.MissionCode, "/steeleagle.ControlService/Land", true, codes.OK, "LOCAL"},
		{"external denied in LOCAL", listener.ExternalCode, "/steeleagle.ControlService/Land", false, codes.PermissionDenied, "LOCAL"},
		{"server control transits back", listener.ServerCode, "/steeleagle.ControlService/Hold", true, codes.OK, "REMOTE"},
	}

	for _, s := range steps {
		called := false
		handler := func(srv any, stream grpc.ServerStream) error {
			called = true
			return nil
		}
		ss := &fakeStream{ctx: codedContext(s.code)}
		err := interceptor(nil, ss, &grpc.StreamServerInfo{FullMethod: s.method}, handler)

		if called != s.called {
			t.Errorf("%s: expected handler called=%v, got %v", s.name, s.called, called)
		}
		if got := status.Code(err); got != s.status {
			t.Errorf("%s: expected status %v, got %v (%v)", s.name, s.status, got, err)
		}
		if p.currentState != s.state {
			t.Errorf("%s: expected state %s, got %s", s.name, s.state, p.currentState)
		}
	}
}

// TestPolicyInterceptorUnknownPeer ensures that requests without a coded peer
// address are treated as unknown and denied.
func TestPolicyInterceptorUnknownPeer(t *testing.T) {
	p := loadTestPolicy(t)
	interceptor := p.NewStreamPolicyInterceptor()

	called := false
	handler := func(srv any, stream grpc.ServerStream) error {
		called = true
		return nil
	}
	ss := &fakeStream{ctx: context.Background()}
	err := interceptor(nil, ss, &grpc.StreamServerInfo{FullMethod: "/steeleagle.ControlService/TakeOff"}, handler)

	if called {
		t.Errorf("expected handler not to be called for unknown peer")
	}
	if status.Code(err) != codes.PermissionDenied {
		t.Errorf("expected PermissionDenied, got %v", err)
	}
}

// TestPolicyInterceptorHandlerError ensures that errors from the handler of
// an approved command are returned unchanged.
func TestPolicyInterceptorHandlerError(t *testing.T) {
	p := loadTestPolicy(t)
	interceptor := p.NewStreamPolicyInterceptor()

	expected := errors.New("handler failed")
	handler := func(srv any, stream grpc.ServerStream) error {
		return expected
	}
	ss := &fakeStream{ctx: codedContext(listener.ServerCode)}
	err := interceptor(nil, ss, &grpc.StreamServerInfo{FullMethod: "/steeleagle.ControlService/TakeOff"}, handler)

	if !errors.Is(err, expected) {
		t.Errorf("expected handler error to be returned, got %v", err)
	}
}

// TestPolicyInterceptorCheckError ensures that requests are denied with an
// internal error when the policy check fails.
func TestPolicyInterceptorCheckError(t *testing.T) {
	// Package name doesn't match the data.policy query, so the check errors
	rego := `package other

import rego.v1

allowed := true
`
	p, err := NewPolicy(simpleLaw(), WithRego(rego), WithLogger(zerolog.Nop()))
	if err != nil {
		t.Fatalf("couldn't create policy: %v", err)
	}
	interceptor := p.NewStreamPolicyInterceptor()

	called := false
	handler := func(srv any, stream grpc.ServerStream) error {
		called = true
		return nil
	}
	ss := &fakeStream{ctx: codedContext(listener.ServerCode)}
	err = interceptor(nil, ss, &grpc.StreamServerInfo{FullMethod: "/steeleagle.ControlService/TakeOff"}, handler)

	if called {
		t.Errorf("expected handler not to be called on policy error")
	}
	if status.Code(err) != codes.Internal {
		t.Errorf("expected Internal, got %v", err)
	}
}

// TestPolicyInterceptorTransitError ensures that an allowed command is still
// denied if the policy fails to transit to its next state.
func TestPolicyInterceptorTransitError(t *testing.T) {
	// Rego allows the command but transits to a state not in the law
	rego := `package policy

import rego.v1

allowed := true
next_state := "MISSING"
`
	p, err := NewPolicy(simpleLaw(), WithRego(rego), WithLogger(zerolog.Nop()))
	if err != nil {
		t.Fatalf("couldn't create policy: %v", err)
	}
	interceptor := p.NewStreamPolicyInterceptor()

	called := false
	handler := func(srv any, stream grpc.ServerStream) error {
		called = true
		return nil
	}
	ss := &fakeStream{ctx: codedContext(listener.ServerCode)}
	err = interceptor(nil, ss, &grpc.StreamServerInfo{FullMethod: "/steeleagle.ControlService/TakeOff"}, handler)

	if called {
		t.Errorf("expected handler not to be called when transit fails")
	}
	if status.Code(err) != codes.Internal {
		t.Errorf("expected Internal, got %v", err)
	}
}

// TestUnaryPolicyInterceptor ensures that the unary interceptor forwards
// permitted commands, denies the rest, and returns the handler's response.
func TestUnaryPolicyInterceptor(t *testing.T) {
	p := loadTestPolicy(t)
	interceptor := p.NewUnaryPolicyInterceptor()

	steps := []struct {
		name   string
		code   listener.AuthCode
		method string
		called bool
		status codes.Code
		state  string
	}{
		{"server allowed", listener.ServerCode, "/steeleagle.ControlService/TakeOff", true, codes.OK, "REMOTE"},
		{"mission denied in REMOTE", listener.MissionCode, "/steeleagle.ControlService/Land", false, codes.PermissionDenied, "REMOTE"},
		{"start mission transits", listener.ServerCode, "/steeleagle.MissionService/StartMission", true, codes.OK, "LOCAL"},
		{"unknown peer denied", listener.UnknownCode, "/steeleagle.ControlService/Land", false, codes.PermissionDenied, "LOCAL"},
	}

	for _, s := range steps {
		called := false
		handler := func(ctx context.Context, req any) (any, error) {
			called = true
			return "response", nil
		}
		resp, err := interceptor(codedContext(s.code), "request", &grpc.UnaryServerInfo{FullMethod: s.method}, handler)

		if called != s.called {
			t.Errorf("%s: expected handler called=%v, got %v", s.name, s.called, called)
		}
		if got := status.Code(err); got != s.status {
			t.Errorf("%s: expected status %v, got %v (%v)", s.name, s.status, got, err)
		}
		if s.called && resp != "response" {
			t.Errorf("%s: expected handler response, got %v", s.name, resp)
		}
		if !s.called && resp != nil {
			t.Errorf("%s: expected nil response on denial, got %v", s.name, resp)
		}
		if p.currentState != s.state {
			t.Errorf("%s: expected state %s, got %s", s.name, s.state, p.currentState)
		}
	}
}
