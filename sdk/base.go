//go:build ignore

package sdk

import (
	"context"
)

type Action interface {
	// Execute performs an action until it is complete or it
	// encounters an error.
	Execute(ctx context.Context, device Device) error
}

type Event interface {
	// Monitor continues to check for an event state until it
	// occurs or encounters an error.
	Monitor(ctx context.Context, device Device) (bool, error)
}
