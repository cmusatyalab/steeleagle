package sdk

import (
	"context"
	"errors"
	"testing"
	"time"

	"github.com/cmusatyalab/steeleagle/sdk/opt"
)

// TestWaiterConstructorErrorSkipsPoll checks that when newWaiter is given a
// non-nil err (e.g. the RPC itself failed to send), Wait short-circuits with
// that error and never invokes the poll function.
func TestWaiterConstructorErrorSkipsPoll(t *testing.T) {
	polled := false
	poll := func(opt.WaitOptions) error {
		polled = true
		return nil
	}
	wantErr := errors.New("rpc failed")
	w := newWaiter(context.Background(), "resp", wantErr, poll)

	// The constructor should have already marked the waiter done, before
	// Wait is ever called
	if done, err := w.Check(); !done || !errors.Is(err, wantErr) {
		t.Fatalf("Check() before Wait() = (%v, %v), want (true, %v)", done, err, wantErr)
	}

	resp, err := w.Wait()
	if resp != "resp" {
		t.Errorf("Wait() resp = %q, want %q", resp, "resp")
	}
	if !errors.Is(err, wantErr) {
		t.Errorf("Wait() err = %v, want %v", err, wantErr)
	}
	if polled {
		t.Errorf("poll function was invoked despite constructor error")
	}

	// Wait's deferred cleanup() runs on top of the constructor's cleanup();
	// sync.Once must make that safe rather than double-closing done
	if done, err := w.Check(); !done || !errors.Is(err, wantErr) {
		t.Fatalf("Check() after Wait() = (%v, %v), want (true, %v)", done, err, wantErr)
	}
}

// TestWaiterWaitReturnsPollResult checks that Wait surfaces both the
// response value and whatever error the poll function returns.
func TestWaiterWaitReturnsPollResult(t *testing.T) {
	wantErr := ErrTimeout
	poll := func(opt.WaitOptions) error { return wantErr }
	w := newWaiter(context.Background(), 42, nil, poll)

	resp, err := w.Wait()
	if resp != 42 { // the answer to life, the universe, and everything...
		t.Errorf("Wait() resp = %v, want 42", resp)
	}
	if !errors.Is(err, wantErr) {
		t.Errorf("Wait() err = %v, want %v", err, wantErr)
	}
}

// TestWaiterCheckReflectsCompletion checks that Check() reports (false, nil)
// while the poll function is still running and only reports done once Wait
// has returned.
func TestWaiterCheckReflectsCompletion(t *testing.T) {
	release := make(chan struct{})
	poll := func(opt.WaitOptions) error {
		<-release
		return nil
	}
	w := newWaiter(context.Background(), "resp", nil, poll)

	if done, _ := w.Check(); done {
		t.Fatalf("Check() = done before poll finished")
	}

	waitDone := make(chan struct{})
	go func() {
		w.Wait()
		close(waitDone)
	}()

	// Give Wait a moment to actually start blocking in the poll function
	time.Sleep(10 * time.Millisecond)
	if done, _ := w.Check(); done {
		t.Fatalf("Check() = done while poll function still blocked")
	}

	close(release)
	<-waitDone

	if done, err := w.Check(); !done || err != nil {
		t.Fatalf("Check() after completion = (%v, %v), want (true, nil)", done, err)
	}
}
