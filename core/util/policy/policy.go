package policy

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"sync"

	"github.com/cmusatyalab/steeleagle/config"
	"github.com/open-policy-agent/opa/rego"
	"github.com/rs/zerolog"
)

// Policy holds the current law state and a Rego query to check the
// law. It is used to enforce law access control to different services.
type Policy struct {
	mu           sync.RWMutex
	currentState string
	query        rego.PreparedEvalQuery
	lawMap       map[string]config.ControlLawState
	log          zerolog.Logger
}

// PolicyDecision marks a decision on whether a command is allowed.
type PolicyDecision struct {
	Allowed   bool   `json:"allowed"`
	NextState string `json:"next_state"`
}

// NewPolicy creates a new policy from a control law and a Rego string.
func NewPolicy(law config.ControlLaw, rego string, opts ...PolicyOption) (*Policy, error) {
	lawMap, err := law.Map()
	if err != nil {
		return nil, err
	}
	regoQuery, err := getRegoQuery(rego)
	if err != nil {
		return nil, err
	}
	p := &Policy{
		currentState: law.First,
		query:        regoQuery,
		lawMap:       lawMap,
		log:          zerolog.New(os.Stdout).With().Timestamp().Logger(),
	}
	for _, opt := range opts {
		opt(p)
	}
	return p, nil
}

// SafeCheckAndTransit checks to see if a command is allowed, and if it is,
// it checks if there is a matching transition. If it matches, transitions
// the policy to the new law state.
func (p *Policy) SafeCheckAndTransit(ctx context.Context, command string) (bool, string, error) {
	p.mu.Lock()
	defer p.mu.Unlock()

	allow, nextState, err := p.check(ctx, command)
	if err != nil {
		p.log.Error().Str("command", command).Msg("command denied")
		return false, p.currentState, err
	} else if nextState != "" {
		p.log.Info().Str("command", command).Str("next", nextState).Msg("found match for command, transiting to new state")
		if err := p.transit(nextState); err != nil {
			p.log.Error().Err(err).Str("command", command).Msg("command denied")
			return false, p.currentState, err
		}
		return allow, nextState, nil
	} else {
		return allow, p.currentState, nil
	}
}

// getRegoQuery gets the Rego query from a string.
func getRegoQuery(regoString string) (rego.PreparedEvalQuery, error) {
	r := rego.New(
		rego.Query("data.policy"),
		rego.Module("check.rego", regoString),
	)
	query, err := r.PrepareForEval(context.Background())
	return query, err
}

// check checks the command against the current control law state's
// allowed statements.
func (p *Policy) check(ctx context.Context, command string) (bool, string, error) {
	results, err := p.query.Eval(ctx, rego.EvalInput(map[string]any{
		"command": command,
		"state":   p.currentState,
		"law":     p.lawMap,
	}))
	if err != nil {
		return false, "", fmt.Errorf("failed to evaluate rego query: %w", err)
	}

	if len(results) == 0 {
		return false, "", fmt.Errorf("got no results back from rego query")
	}

	raw := results[0].Expressions[0].Value
	str, err := json.Marshal(raw)
	if err != nil {
		return false, "", err
	}

	d := &PolicyDecision{}
	if err := json.Unmarshal(str, d); err != nil {
		return false, "", err
	}

	return d.Allowed, d.NextState, nil
}

// transit transits the policy to a new control law state.
func (p *Policy) transit(nextState string) error {
	_, ok := p.lawMap[nextState]
	if ok {
		p.currentState = nextState
	} else {
		return fmt.Errorf("failed to transition to state %s, not in law!", nextState)
	}
	return nil
}
