package sdk

import (
	"context"
	"time"
)

// pollFunc checks the current status of an operation. It should return
// true along with the error once the operation has finished.
type pollFunc func(ctx context.Context) (bool, error)

// waiter represents an in-flight long-running operation.
type waiter struct {
	ctx      context.Context
	poll     pollFunc
	err      error
	interval time.Duration
}

// newWaiter creates a waiter object that checks the status of an in-flight
// RPC, returning the result once it is complete.
func newWaiter(ctx context.Context, poll pollFunc, err error) *waiter {
	return &waiter{ctx: ctx, poll: poll, err: err, interval: 500 * time.Millisecond}
}

// WithPollInterval sets the initial delay between status checks.
func (w *waiter) WithPollInterval(d time.Duration) *waiter {
	w.interval = d
	return w
}

// Wait blocks until the operation completes, ctx is done, or polling fails.
func (w *waiter) Wait() error {
	if w.err != nil {
		return w.err
	}
	interval := w.interval
	for {
		done, err := w.poll(w.ctx)
		if err != nil || done {
			return err
		}
		select {
		case <-w.ctx.Done():
			return w.ctx.Err()
		case <-time.After(interval):
		}
	}
}
