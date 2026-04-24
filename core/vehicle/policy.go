package vehicle

import (
    "fmt"
    "sync"
    "context"
    "encoding/json"

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
    mu sync.RWMutex
    currentState string
    query rego.PreparedEvalQuery
    lawMap map[string]ControlLawState
    acl    map[string]
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
        query: regoQuery,
        lawMap: laws,
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

func (i *policyState) safeCheckAndTransit(ctx context.Context, command string) (bool, string, error) {
    i.mu.Lock()
    defer i.mu.Unlock()

    allow, nextState, err := i.check(ctx, command)
    if err != nil {
        return false, "", err
    } else if nextState != "" {
        return allow, nextState, i.transit(nextState)
    }

    return allow, nextState, nil
}

func (i *policyState) check(ctx context.Context, command string) (bool, string, error) {
    log.Debug().Str("command", command).Msg("command check started")
    results, err := i.query.Eval(ctx, rego.EvalInput(map[string]any{
		"command": command,
        "state": i.currentState,
        "law": i.lawMap,
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

func (i *policyState) transit(nextState string) error {
    _, ok := i.lawMap[nextState]
    if ok {
        log.Info().Str("state", nextState).Msg("transitioning to new control state")
        i.currentState = nextState
    } else {
        return fmt.Errorf("failed to transition to state %s, not in law!", nextState)
    }
    return nil
}
