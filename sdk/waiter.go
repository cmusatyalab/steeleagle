package sdk

import (
	"sync"
	"time"
)

// Waiter represents an in-flight long-running operation, returned by every
// Vehicle command. Wait blocks until the operation completes; Check reports
// whether it has, from another goroutine. A Waiter must not be waited on
// by more than one goroutine.
type Waiter[Resp any] struct {
	poll pollFunc
	resp Resp
	err  error
	once sync.Once
	done chan struct{}
}

// WaitOptions are the options for a waiter, the poll interval and the
// timeout. Timeout set to zero means that the Wait will never time out.
type WaitOptions struct {
	Interval   time.Duration // time between polls
	Timeout    time.Duration // deadline for RPC
	Stall      time.Duration // timeout for making forward progress
	Tolerances Tolerances    // error tolerance for final destination check
}

// Tolerances are the tolerances waiters use to decide when a command has
// satisfied its expectation.
type Tolerances struct {
	PosTol      float32 // position tolerance
	AngleTol    float32 // angle tolerance
	SpeedTol    float32 // speed tolerance
	AngSpeedTol float32 // angular speed tolerance
}

// newWaiter creates a waiter object that checks the status of an in-flight
// RPC, returning the result once it is complete. A non-nil err means the
// RPC failed, so there is nothing to wait on.
func newWaiter[Resp any](resp Resp, err error, poll pollFunc) *Waiter[Resp] {
	w := &Waiter[Resp]{
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

// Wait blocks until the operation completes, the vehicle's context is
// done, or polling fails, and returns the response along with the error
// the operation ended with. Once the operation is done, Wait returns the
// same result again without polling.
func (w *Waiter[Resp]) Wait(options ...WaitOption) (Resp, error) {
	select {
	case <-w.done:
		return w.resp, w.err
	default:
	}

	// Apply options
	opts := WaitOptions{
		Interval: 100 * time.Millisecond,
		Stall:    5 * time.Second,
		Tolerances: Tolerances{
			PosTol:      3.0, // meters
			AngleTol:    5.0, // degrees
			SpeedTol:    0.5, // meters/second
			AngSpeedTol: 5.0, // degrees/second
		},
	}
	for _, option := range options {
		option(&opts)
	}

	// Record the outcome before marking the operation done, so Check sees
	// it
	w.err = w.poll(opts)
	w.cleanup()
	return w.resp, w.err
}

// Check checks whether the operation has completed, and if so with what
// error: the RPC's error, or else the error waiting for it ended with.
func (w *Waiter[Resp]) Check() (bool, error) {
	select {
	case <-w.done:
		return true, w.err // safe read, happens after close(done)
	default:
		return false, nil // not done yet
	}
}

// cleanup closes the done channel in a safe way.
func (w *Waiter[Resp]) cleanup() {
	w.once.Do(func() {
		close(w.done)
	})
}
