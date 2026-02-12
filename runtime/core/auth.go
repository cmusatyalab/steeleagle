package core

import (
    "fmt"
    "os"
    "sync"
    "context"
    "encoding/json"
    "path/filepath"

    "github.com/open-policy-agent/opa/rego"
)

type policyState struct {
    stateMu sync.Mutex
    currentState string
    query rego.PreparedEvalQuery
    test bool
    lawMap map[string]controlLawState
}

type policyDecision struct {
    Allowed   bool   `json:"allowed"`
	NextState string `json:"next_state"`
}

func getRegoPolicy(isTesting bool) rego.PreparedEvalQuery {
    // Ignore reading config directory if in test mode 
    if isTesting {
        return getDefaultRegoPolicy()
    }

    configDir, err := os.UserConfigDir()
    if err != nil {
        logger.Warn("OS config directory could not be found, using default rego policy", "error", err)
        return getDefaultRegoPolicy()
    }

    appDir := filepath.Join(configDir, ApplicationName)
    configPath := filepath.Join(appDir, RegoFilename)
    
    data, err := os.ReadFile(configPath)
    if err != nil {
        logger.Warn("could not find rego policy file, using default policy", "error", err)
        return getDefaultRegoPolicy()
    }

    r := rego.New(
        rego.Query("data.policy"),
        rego.Module("policy.rego", string(data)),
    )
    query, err := r.PrepareForEval(context.Background())
    if err != nil {
        logger.Warn("something went wrong preparing rego policy from file, using default policy", "error", err)
        return getDefaultRegoPolicy()
    }

    return query
}

func getDefaultRegoPolicy() rego.PreparedEvalQuery {
    r := rego.New(
        rego.Query("data.policy"),
        rego.Module("policy.rego", DefaultRego),
    )
    query, err := r.PrepareForEval(context.Background())
    if err != nil {
        panic(err)
    }
    
    return query
}

func (i *policyState) safeCheckAndTransit(ctx context.Context, command string) (bool, string, error) {
    i.stateMu.Lock()
    defer i.stateMu.Unlock()

    allow, nextState, err := i.check(ctx, command)
    if err != nil {
        return false, "", err
    } else if nextState != "" {
        return allow, nextState, i.transit(nextState)
    }

    return allow, nextState, nil
}

func (i *policyState) check(ctx context.Context, command string) (bool, string, error) {
    logger.Debug("command check started", "command", command)
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

    logger.Debug("command check completed", "command", command, "allowed", d.Allowed, "next_state", d.NextState)
    return d.Allowed, d.NextState, nil
}

func (i *policyState) transit(nextState string) error {
    _, ok := i.lawMap[nextState]
    if ok {
        logger.Info("transitioning to new control state", "state", nextState)
        i.currentState = nextState
    } else {
        return fmt.Errorf("failed to transition to state %s, not in law!", nextState)
    }
    return nil
}
