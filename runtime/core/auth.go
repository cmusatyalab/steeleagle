package core

import (
    "fmt"
    "os"
    "log/slog"
    "net"
    "sync"
    "context"
    "encoding/json"
    "path/filepath"
    "strings"

    "google.golang.org/grpc/peer"
    "google.golang.org/grpc/metadata"
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

func getRegoPolicy() rego.PreparedEvalQuery {
    configDir, err := os.UserConfigDir()
    if err != nil {
        slog.Warn("OS config directory could not be found, using default rego policy", "error", err)
        return getDefaultRegoPolicy()
    }

    appDir := filepath.Join(configDir, ApplicationName)
    configPath := filepath.Join(appDir, RegoFilename)
    
    data, err := os.ReadFile(configPath)
    if err != nil {
        slog.Warn("could not find rego policy file, using default policy", "error", err)
        return getDefaultRegoPolicy()
    }

    r := rego.New(
        rego.Query("data.policy"),
        rego.Module("policy.rego", string(data)),
    )
    query, err := r.PrepareForEval(context.Background())
    if err != nil {
        slog.Warn("something went wrong preparing rego policy from file, using default policy", "error", err)
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

    allow, nextState, cleanedCommand, err := i.check(ctx, command)
    if err != nil {
        return false, cleanedCommand, err
    } else if nextState != "" {
        return allow, cleanedCommand, i.transit(nextState)
    }

    return allow, cleanedCommand, nil
}

func (i *policyState) check(ctx context.Context, command string) (bool, string, string, error) {
    // If we are in test mode, we can set our peer type to test the policy
    peer := "unknown"
    if i.test {
        md, ok := metadata.FromIncomingContext(ctx)
        if !ok {
            peer = getPeer(ctx)
        } else if identity, exists := md["identity"]; exists {
            if len(identity) > 0 {
                peer = identity[0]
            } else {
                peer = getPeer(ctx)
            }
        }
    } else {
        peer = getPeer(ctx)
    }

    splits := strings.Split(command, ".")
    cleanedCommand := fmt.Sprintf("%s/%s", peer, splits[len(splits) - 1])
    results, err := i.query.Eval(ctx, rego.EvalInput(map[string]any{
		"command": cleanedCommand,
        "state": i.currentState,
        "law": i.lawMap,
	}))

    if len(results) == 0 {
		return false, "", cleanedCommand, fmt.Errorf("got no results back from rego query")
	}

    raw := results[0].Expressions[0].Value
	str, err := json.Marshal(raw)
    if err != nil {
		return false, "", cleanedCommand, err
	}

    d := &policyDecision{}
	if err := json.Unmarshal(str, d); err != nil {
		return false, "", cleanedCommand, err
	}

    return d.Allowed, d.NextState, cleanedCommand, nil
}

func (i *policyState) transit(nextState string) error {
    _, ok := i.lawMap[nextState]
    if ok {
        i.currentState = nextState
    } else {
        return fmt.Errorf("failed to transition to state %s, not in law!", nextState)
    }
    return nil
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
