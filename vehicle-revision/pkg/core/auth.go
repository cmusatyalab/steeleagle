package core

import (
    "fmt"
    "sync"
    "context"
    "encoding/json"
    "path/filepath"

    "github.com/open-policy-agent/opa/rego"
)

type policyDecision struct {
    allow     bool   `json:"allow"`
	nextState string `json:"next_state"`
}

type policyState struct {
    state string
    stateMu sync.Mutex
    lawJSON map[string]any
    query rego.PreparedEvalQuery
}

func getRegoPolicy() rego.PreparedEvalQuery {
    configDir, err := os.UserConfigDir()
    if err != nil {
        slog.warn("OS config directory could not be found! Using default Rego policy.")
        return getDefaultRegoPolicy()
    }

    appDir := filepath.join(configDir, ApplicationName)
    configPath := filepath.Join(appDir, RegoFilename)
    
    data, err := os.ReadFile(configPath)
    if err != nil {
        slog.warn(fmt.Sprintf("Could not find Rego policy file %s:\n%v\nUsing default Rego policy.", configPath, err))
        return getDefaultRegoPolicy()
    }

    r := rego.New(
        rego.Query("data.policy.result"),
        rego.Module("policy.rego", string(data)),
    )
    query, err := r.PrepareForEval(context.Background())
    if err != nil {
        slog.warn(fmt.Sprintf("Something went wrong preparing Rego policy from file %s:\n%v\nUsing default policy.", configPath, err))
        return getDefaultRegoPolicy()
    }

    return query
}

func getDefaultRegoPolicy() rego.PreparedEvalQuery {
    r := rego.New(
        rego.Query("data.policy.result"),
        rego.Module("policy.rego", DefaultRego),
    )
    query, err := r.PrepareForEval(context.Background())
    if err != nil {
        panic(err)
    }
    
    return query
}

func (i *policyState) safeCheckAndTransit(ctx context.Context, command string) (bool, error) {
    i.stateMu.Lock()
    defer i.stateMu.Unlock()

    allow, nextState, err := i.check(ctx, command)
    if err != nil {
        return false, err
    } else if nextState != "" {
        return true, i.transit(nextState)
    }
}

func (i *policyState) check(ctx context.Context, command string) (bool, string, error) {
    results, err := i.query.Eval(ctx, rego.EvalInput(map[string]any{
		"command": command,
        "law": i.lawJSON,
        "peer": getPeer(ctx)
	}))

    if len(results) == 0 {
		return false, "", nil
	}

    raw := results[0].Expressions[0].Value
	bytes, err := json.Marshal(raw)
    if err != nil {
		return false, "", err
	}

	var d policyDecision
	if err := json.Unmarshal(bytes, &d); err != nil {
		return false, "", err
	}
    
    return d.allow, d.nextState, nil
}

func (i *policyState) transit(nextState string) error {
    value, ok = i.lawJSON[nextState]
    if ok {
        i.state = nextState
    } else {
        return fmt.Errorf("failed to transition to state %s, not in law!", nextState)
    }
}

func getPeer(ctx context.Context) string {
	p, ok := peer.FromContext(ctx)
	if !ok || p.Addr == nil {
		return "unknown"
	}

	switch addr := p.Addr.(type) {
	case *net.TCPAddr:
		if addr.IP.IsLoopback() {
			return "internal"
		}
		return "server"
	case *net.UnixAddr:
		return "internal"
	default:
		if addr.Network() == "pipe" {
            return "kernel"
        } else {
            return "unknown"
        }
	}
}
