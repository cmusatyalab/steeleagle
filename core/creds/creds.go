package creds

import "fmt"

type EntityID string

const (
    Driver   EntityID = "driver"
    Mission  EntityID = "mission"
    Internal EntityID = "internal"
    Server   EntityID = "server"
    Engine   EntityID = "engine"
    External EntityID = "external"
)

type contextKey struct {}
type Credentials struct {
    ID       EntityID
}

func (i *Credentials) Qualify(string fullMethodName) string {
    return fmt.Sprintf("%s%s", i.ID, fullMethodName)
}

func Inject(ctx context.Context, creds Credentials) context.Context {
    return context.WithValue(ctx, contextKey{}, creds)
}

func Extract(ctx context.Context) (Credentials, bool) {
    creds, ok := ctx.Value(contextKey{}).(ConnMeta)
    return creds, ok
}
