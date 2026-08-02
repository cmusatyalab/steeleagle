package sdk

import (
	"context"
	"sync"
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
	once     sync.Once
	done     chan struct{}
}

// newWaiter creates a waiter object that checks the status of an in-flight
// RPC, returning the result once it is complete.
func newWaiter(ctx context.Context, poll pollFunc, err error) *waiter {
	w := &waiter{
		ctx:      ctx,
		poll:     poll,
		err:      err,
		interval: 500 * time.Millisecond,
		done:     make(chan struct{}),
	}
	if err != nil {
		w.cleanup() // want to indicate that there is nothing to wait on
	}
	return w
}

// WithPollInterval sets the initial delay between status checks.
func (w *waiter) WithPollInterval(d time.Duration) *waiter {
	w.interval = d
	return w
}

// Wait blocks until the operation completes, ctx is done, or polling fails.
func (w *waiter) Wait() error {
	defer w.cleanup()
	if w.err != nil {
		return w.err
	}
	interval := w.interval
	for {
		done, err := w.poll(w.ctx)
		if err != nil || done {
			w.err = err
			return err
		}
		select {
		case <-w.ctx.Done():
			w.err = w.ctx.Err()
			return w.ctx.Err()
		case <-time.After(interval):
		}
	}
}

// Check checks whether the operation has completed, and if so with what error.
func (w *waiter) Check() (bool, error) {
	select {
	case <-w.done:
		return true, w.err // safe read, happens after close(done)
	default:
		return false, nil // not done yet
	}
}

// cleanup closes the done channel in a safe way.
func (w *waiter) cleanup() {
	w.once.Do(func() {
		close(w.done)
	})
}
