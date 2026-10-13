package sdk

import (
	"errors"
	"testing"
	"time"
)

// TestWaiterConstructorErrorSkipsPoll checks that when newWaiter is given a
// non-nil err (e.g. the RPC itself failed to send), Wait short-circuits with
// that error and never invokes the poll function.
func TestWaiterConstructorErrorSkipsPoll(t *testing.T) {
	polled := false
	poll := func(WaitOptions) error {
		polled = true
		return nil
	}
	wantErr := errors.New("rpc failed")
	w := newWaiter("resp", wantErr, poll)

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
	poll := func(WaitOptions) error { return wantErr }
	w := newWaiter(42, nil, poll)

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
	poll := func(WaitOptions) error {
		<-release
		return nil
	}
	w := newWaiter("resp", nil, poll)

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

// TestWaiterCheckReportsPollError checks that once Wait has returned, Check
// reports the error polling ended with, not just the RPC's, and that a
// second Wait returns the same result without polling again.
func TestWaiterCheckReportsPollError(t *testing.T) {
	polls := 0
	poll := func(WaitOptions) error {
		polls++
		return ErrTimeout
	}
	w := newWaiter("resp", nil, poll)

	if _, err := w.Wait(); !errors.Is(err, ErrTimeout) {
		t.Fatalf("Wait() err = %v, want %v", err, ErrTimeout)
	}
	if done, err := w.Check(); !done || !errors.Is(err, ErrTimeout) {
		t.Errorf("Check() = (%v, %v), want (true, %v)", done, err, ErrTimeout)
	}
	if resp, err := w.Wait(); resp != "resp" || !errors.Is(err, ErrTimeout) {
		t.Errorf("second Wait() = (%q, %v), want (%q, %v)", resp, err, "resp", ErrTimeout)
	}
	if polls != 1 {
		t.Errorf("poll ran %d times, want once", polls)
	}
}
