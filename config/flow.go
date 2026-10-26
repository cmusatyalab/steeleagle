package config

import (
	"bytes"
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/BurntSushi/toml"
)

// Engine locations in a flow: served by the local compute service, or by the
// remote one.
const (
	LocationLocal  = "local"
	LocationRemote = "remote"
)

type Producer struct {
	// Name of the producer
	Name string `toml:"name"`
	// Number of inputs the producer may have in the flow at once (optional,
	// must be at least 1, defaults to Uriel's default)
	Tokens *int `toml:"tokens,omitempty"`
}

type Engine struct {
	// Name of the engine
	Name string `toml:"name"`
	// Location string (one of: local, remote)
	Location string `toml:"location"`
}

type Edge struct {
	// Start node, a producer or an engine
	From string `toml:"from"`
	// End node, an engine
	To string `toml:"to"`
	// Timeout string literal ("2s", e.g.), must be positive
	Timeout string `toml:"timeout"`
}

// FlowConfig is a dataflow, in the form of a Uriel flow spec. Uriel rejects
// any key it does not know, so a flow has no keys beyond these.
type FlowConfig struct {
	// Flow graph producers
	Producers []Producer `toml:"producers"`
	// Flow graph engines
	Engines []Engine `toml:"engines"`
	// Flow graph edges
	Edges []Edge `toml:"edges"`
}

// ParseFlowConfigFromBytes parses a flow config from a TOML byte slice.
func ParseFlowConfigFromBytes(content []byte) (*FlowConfig, error) {
	f := &FlowConfig{}
	meta, err := toml.Decode(string(content), f)
	if err != nil {
		return nil, err
	}
	// The flow is handed to Uriel as written, so unknown keys are rejected
	// here rather than when the flow is set
	if undecoded := meta.Undecoded(); len(undecoded) > 0 {
		keys := make([]string, len(undecoded))
		for i, k := range undecoded {
			keys[i] = k.String()
		}
		return nil, fmt.Errorf("unknown flow keys %s", strings.Join(keys, ", "))
	}
	if err := f.Validate(); err != nil {
		return nil, err
	}
	return f, nil
}

// ParseFlowConfigFromFilepath parses a flow config from a filepath.
func ParseFlowConfigFromFilepath(filepath string) (*FlowConfig, error) {
	content, err := os.ReadFile(filepath)
	if err != nil {
		return nil, err
	}
	return ParseFlowConfigFromBytes(content)
}

// ToBytes writes a FlowConfig to TOML bytes.
func (f *FlowConfig) ToBytes() ([]byte, error) {
	var buf bytes.Buffer
	if err := toml.NewEncoder(&buf).Encode(f); err != nil {
		return nil, err
	}
	return buf.Bytes(), nil
}

// Validate checks the flow as Uriel does: node names are non-empty and unique
// across producers and engines, producers have at least 1 token and feed an
// engine, engines have a known location, and edges lead from a node to an
// engine, appear once, have a positive timeout and form no cycle.
func (f *FlowConfig) Validate() error {
	nodes := make(map[string]struct{}, len(f.Producers)+len(f.Engines))
	addNode := func(kind, name string) error {
		if name == "" {
			return fmt.Errorf("%s name is empty", kind)
		}
		if _, ok := nodes[name]; ok {
			return fmt.Errorf("%q names two nodes of the flow", name)
		}
		nodes[name] = struct{}{}
		return nil
	}
	for _, p := range f.Producers {
		if err := addNode("producer", p.Name); err != nil {
			return err
		}
		if p.Tokens != nil && *p.Tokens < 1 {
			return fmt.Errorf("producer %q needs at least 1 token", p.Name)
		}
	}
	engines := make(map[string]struct{}, len(f.Engines))
	for _, e := range f.Engines {
		if err := addNode("engine", e.Name); err != nil {
			return err
		}
		engines[e.Name] = struct{}{}
		if e.Location != LocationLocal && e.Location != LocationRemote {
			return fmt.Errorf("engine %q has location %q, must be %q or %q",
				e.Name, e.Location, LocationLocal, LocationRemote)
		}
	}

	type edgeKey struct{ from, to string }
	edges := make(map[edgeKey]struct{}, len(f.Edges))
	next := make(map[string][]string)
	for _, e := range f.Edges {
		if _, ok := nodes[e.From]; !ok {
			return fmt.Errorf("edge starts at %q, which is not in the flow", e.From)
		}
		if _, ok := engines[e.To]; !ok {
			return fmt.Errorf("edge leads to %q, which is not an engine of the flow", e.To)
		}
		key := edgeKey{e.From, e.To}
		if _, ok := edges[key]; ok {
			return fmt.Errorf("the edge from %q to %q appears twice", e.From, e.To)
		}
		edges[key] = struct{}{}
		timeout, err := time.ParseDuration(e.Timeout)
		if err != nil {
			return fmt.Errorf("the edge from %q to %q has invalid timeout %q: %w", e.From, e.To, e.Timeout, err)
		}
		if timeout <= 0 {
			return fmt.Errorf("the edge from %q to %q needs a positive timeout", e.From, e.To)
		}
		next[e.From] = append(next[e.From], e.To)
	}
	for _, p := range f.Producers {
		if len(next[p.Name]) == 0 {
			return fmt.Errorf("producer %q feeds no engine", p.Name)
		}
	}
	return acyclic(f.Engines, next)
}

// acyclic returns an error if the edges in next form a cycle through any of
// engines. Producers have no edges into them, so a cycle is only of engines.
func acyclic(engines []Engine, next map[string][]string) error {
	const (
		unvisited = iota
		visiting
		done
	)
	state := make(map[string]int, len(engines))
	var visit func(string) error
	visit = func(name string) error {
		switch state[name] {
		case visiting:
			return fmt.Errorf("the edges form a cycle through %q", name)
		case done:
			return nil
		}
		state[name] = visiting
		for _, to := range next[name] {
			if err := visit(to); err != nil {
				return err
			}
		}
		state[name] = done
		return nil
	}
	for _, e := range engines {
		if err := visit(e.Name); err != nil {
			return err
		}
	}
	return nil
}
