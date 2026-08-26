package preprocess

import "testing"

// TestBlockStackTopAndSizeEmpty tests a basic call to top on
// an empty stack, verifying it defaults to false, and checks
// that size is zero.
func TestBlockStackTopAndSizeEmpty(t *testing.T) {
	var b blockStack
	if b.top() {
		t.Error("top() on empty stack = true, want false")
	}
	if b.size() != 0 {
		t.Errorf("size() on empty stack = %d, want 0", b.size())
	}
}

// TestBlockStackPush tests a basic push of true to the stack.
func TestBlockStackPush(t *testing.T) {
	var b blockStack
	b.push(true)
	if !b.top() {
		t.Error("top() after push(true) = false, want true")
	}
	if b.size() != 1 {
		t.Errorf("size() = %d, want 1", b.size())
	}
}

// TestBlockStackDominance checks that nce a true value is on the stack,
// pushing false on top of it still reports true since nested blocks
// don't un-satisfy an outer satisfied block.
func TestBlockStackDominance(t *testing.T) {
	var b blockStack
	b.push(true)
	b.push(false)
	if !b.top() {
		t.Error("top() = false after push(false) on top of push(true), want true (dominance)")
	}
	if b.size() != 2 {
		t.Errorf("size() = %d, want 2", b.size())
	}
}

// TestBlockStackPopRestoresPrevious checks for expected stack behavior,
// that a push of two values and then a pop returns the first on a top call.
func TestBlockStackPopRestoresPrevious(t *testing.T) {
	var b blockStack
	b.push(false)
	b.push(true)
	if err := b.pop(); err != nil {
		t.Fatalf("pop() returned error: %v", err)
	}
	if b.top() {
		t.Error("top() = true after popping the true entry, want false")
	}
	if b.size() != 1 {
		t.Errorf("size() = %d, want 1", b.size())
	}
}

// TestBlockStackPopEmptyErrors checks that a pop call on an empty stack
// returns an error.
func TestBlockStackPopEmptyErrors(t *testing.T) {
	var b blockStack
	if err := b.pop(); err == nil {
		t.Error("pop() on empty stack returned nil error, want an error")
	}
	if b.size() != 0 {
		t.Errorf("size() after failed pop = %d, want 0", b.size())
	}
}

// TestBlockStackPushAfterDrain makes sure that a stack drained back to
// empty behaves exactly like a fresh stack.
func TestBlockStackPushAfterDrain(t *testing.T) {
	var b blockStack
	b.push(true)
	if err := b.pop(); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if b.size() != 0 {
		t.Fatalf("size() = %d, want 0", b.size())
	}
	b.push(false)
	if b.top() {
		t.Error("top() = true after push(false) on drained stack, want false")
	}
	if b.size() != 1 {
		t.Errorf("size() = %d, want 1", b.size())
	}
}
