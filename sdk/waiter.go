package sdk

import (
	"context"
	"fmt"
	"sync"
	"time"
)

// pollFunc checks the current status of an operation. It should return
// true along with the error once the operation has finished.
type pollFunc func(ctx context.Context) (bool, error)

// waiterOption are options for configuring a waiter.
type waiterOption func(waiterConfigurer)

// waiterConfigurer is a generic interface for setting members of the waiter without requiring
// type templating.
type waiterConfigurer interface {
	setInterval(time.Duration)
	setTimeout(time.Duration)
}

// WithPollInterval changes the poll interval for the waiter.
func WithPollInterval(t time.Duration) waiterOption {
	return func(w waiterConfigurer) {
		w.setInterval = t
	}
}

// WithTimeout changes the timeout duration before the waiter returns an error.
func WithTimeout(t time.Duration) waiterOption {
	return func(w waiterConfigurer) {
		w.setTimeout = t
	}
}

// waiter represents an in-flight long-running operation.
type waiter[Resp any] struct {
	ctx      context.Context
	poll     pollFunc
	resp     Resp
	err      error
	interval time.Duration
	timeout  time.Duration
	once     sync.Once
	done     chan struct{}
}

// newWaiter creates a waiter object that checks the status of an in-flight
// RPC, returning the result once it is complete.
func newWaiter[Resp any](ctx context.Context, resp Resp, poll pollFunc, err error, options ...waiterOption) *waiter[Resp] {
	w := &waiter{
		ctx:      ctx,
		poll:     pollFun,
		resp:     resp,
		err:      err,
		interval: 100 * time.Millisecond,
		done:     make(chan struct{}),
	}
	for _, option := range options {
		option(w)
	}
	if err != nil {
		w.cleanup() // want to indicate that there is nothing to wait on
	}
	return w
}

// Wait blocks until the operation completes, ctx is done, or polling fails.
func (w *waiter[Resp]) Wait() (Resp, error) {
	defer w.cleanup()
	if w.err != nil {
		return w.resp, w.err
	}
	for {
		done, err := w.poll(w.ctx)
		if err != nil || done {
			w.err = err
			return w.resp, err
		}
		if w.timeout {
			select {
			case <-w.ctx.Done():
				w.err = w.ctx.Err()
				return w.resp, w.ctx.Err()
			case <-time.After(w.timeout):
				return w.resp, fmt.Errorf("timeout reached before command completed")
			case <-time.After(w.interval):
			}
		} else {
			select {
			case <-w.ctx.Done():
				w.err = w.ctx.Err()
				return w.resp, w.ctx.Err()
			case <-time.After(w.interval):
			}
		}
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

// setInterval is an internal set method for waiter to satisfy the configurer interface.
func (*waiter[Resp]) setInterval(t time.Duration) {
	w.interval = t
}

// setTimeout is an internal set method for waiter to satisfy the configurer interface.
func (*waiter[Resp]) setTimeout(t time.Duration) {
	w.timeout = t
}

// cleanup closes the done channel in a safe way.
func (w *waiter[Resp]) cleanup() {
	w.once.Do(func() {
		close(w.done)
	})
}
