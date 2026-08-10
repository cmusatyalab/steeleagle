//go:build ignore

package sdk

import (
	"context"
	"sync"
	"time"

	"github.com/cmusatyalab/steeleagle/sdk/opt"
)

// waiter represents an in-flight long-running operation.
type waiter[Resp any] struct {
	ctx  context.Context
	poll pollFunc
	resp Resp
	err  error
	once sync.Once
	done chan struct{}
}

// newWaiter creates a waiter object that checks the status of an in-flight
// RPC, returning the result once it is complete.
func newWaiter[Resp any](ctx context.Context, resp Resp, err error, poll pollFunc) *waiter[Resp] {
	w := &waiter[Resp]{
		ctx:  ctx,
		poll: poll,
		resp: resp,
		err:  err,
		done: make(chan struct{}),
	}
	if err != nil {
		w.cleanup() // want to indicate that there is nothing to wait on
	}
	return w
}

// Wait blocks until the operation completes, ctx is done, or polling fails.
func (w *waiter[Resp]) Wait(options ...opt.WaitOption) (Resp, error) {
	defer w.cleanup()

	// Apply options
	opts := opt.WaitOptions{
		Interval: 100 * time.Millisecond,
		Stall:    1 * time.Second,
		Tolerances: opt.Tolerances{
			PosTol:      0.5, // meters
			AngleTol:    2.0, // degrees
			SpeedTol:    0.5, // meters/second
			AngSpeedTol: 0.5, // degrees/second
		},
	}
	for _, option := range options {
		option(&opts)
	}

	if w.err != nil {
		return w.resp, w.err
	} else {
		return w.resp, poll(opts)
	}
}

// Check checks whether the operation has completed, and if so with what error.
func (w *waiter[Resp]) Check() (bool, error) {
	select {
	case <-w.done:
		return true, w.err // safe read, happens after close(done)
	default:
		return false, nil // not done yet
	}
}

// cleanup closes the done channel in a safe way.
func (w *waiter[Resp]) cleanup() {
	w.once.Do(func() {
		close(w.done)
	})
}
