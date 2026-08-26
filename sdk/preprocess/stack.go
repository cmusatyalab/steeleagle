package preprocess

import "fmt"

// blockStack is a stack implementation for tracking a directive block
// like begin-exclude or begin-private. It holds the last directive value
// and implements directive dominance within its push method.
type blockStack struct {
	stack []bool
}

// push adds an item to the block stack, overwriting its value with
// the previous top if the previous top was true. This follows directive
// dominance semantics.
func (b *blockStack) push(item bool) {
	b.stack = append(b.stack, b.top() || item)
}

// pop removes the top element of the block stack and throws an
// error if the stack is empty.
func (b *blockStack) pop() error {
	if len(b.stack) == 0 {
		return fmt.Errorf("attempted to pop an empty block stack")
	}
	b.stack = b.stack[:len(b.stack)-1]
	return nil
}

// top reads the top element of the block stack, returning false
// if the stack is empty (default value).
func (b *blockStack) top() bool {
	if len(b.stack) == 0 {
		return false
	} else {
		return b.stack[len(b.stack)-1]
	}
}

// size gets the current size of the stack.
func (b *blockStack) size() int {
	return len(b.stack)
}
