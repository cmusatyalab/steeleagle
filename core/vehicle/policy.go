package vehicle

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"

	"github.com/open-policy-agent/opa/rego"
	"github.com/rs/zerolog/log"
)

type PolicyConfig struct {
	// Control laws to use for RPC authorization policy
	Server      string
	ExternalIPs []string
	Law         ControlLaw
}

type policyState struct {
	mu           sync.RWMutex
	currentState string
	query        rego.PreparedEvalQuery
	lawMap       map[string]ControlLawState
}

type policyDecision struct {
	Allowed   bool   `json:"allowed"`
	NextState string `json:"next_state"`
}

func getPolicy(policyCfg PolicyConfig) policyState {
	laws, first := getLaw(&policyCfg.Law)
	regoQuery := getRegoQuery()
	return policyState{
		currentState: first,
		query:        regoQuery,
		lawMap:       laws,
	}
}

func getRegoQuery() rego.PreparedEvalQuery {
	r := rego.New(
		rego.Query("data.policy"),
		rego.Module("check.rego", DefaultRego),
	)
	query, err := r.PrepareForEval(context.Background())
	if err != nil {
		panic(err)
	}

	return query
}

func (p *policyState) safeCheckAndTransit(ctx context.Context, command string) (bool, string, error) {
	p.mu.Lock()
	defer p.mu.Unlock()

	allow, nextState, err := p.check(ctx, command)
	if err != nil {
		return false, "", err
	} else if nextState != "" {
		return allow, nextState, p.transit(nextState)
	}

	return allow, nextState, nil
}

func (p *policyState) check(ctx context.Context, command string) (bool, string, error) {
	log.Debug().Str("command", command).Msg("command check started")
	results, err := p.query.Eval(ctx, rego.EvalInput(map[string]any{
		"command": command,
		"state":   p.currentState,
		"law":     p.lawMap,
	}))

	if len(results) == 0 {
		return false, "", fmt.Errorf("got no results back from rego query")
	}

	raw := results[0].Expressions[0].Value
	str, err := json.Marshal(raw)
	if err != nil {
		return false, "", err
	}

	d := &policyDecision{}
	if err := json.Unmarshal(str, d); err != nil {
		return false, "", err
	}

	log.Debug().Str("command", command).Bool("allowed", d.Allowed).Str("next_state", d.NextState).Msg("command check completed")
	return d.Allowed, d.NextState, nil
}

func (p *policyState) transit(nextState string) error {
	_, ok := p.lawMap[nextState]
	if ok {
		log.Info().Str("state", nextState).Msg("transitioning to new control state")
		p.currentState = nextState
	} else {
		return fmt.Errorf("failed to transition to state %s, not in law!", nextState)
	}
	return nil
}
