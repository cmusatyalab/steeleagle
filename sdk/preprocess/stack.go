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

// replaceFrame is a single open begin-replace block.
type replaceFrame struct {
	fired   bool // whether the directive fired (a tagged type is unsupported)
	inWith  bool // whether #replace-with has been seen for this block
	dropped bool // whether an enclosing block already drops this whole block
}

// replaceStack is a stack implementation for tracking begin-replace blocks.
// Each block has two sections: the original (begin to replace-with) and the
// replacement (replace-with to end). Exactly one section is kept, and a
// dropped section dominates any blocks nested inside of it.
type replaceStack struct {
	stack []replaceFrame
}

// push opens a new replace block, inheriting dominance from the current top.
func (r *replaceStack) push(fired bool) {
	r.stack = append(r.stack, replaceFrame{fired: fired, dropped: r.drop()})
}

// with switches the top block to its replacement section, throwing an error
// if there is no open block or the block has already switched.
func (r *replaceStack) with() error {
	if len(r.stack) == 0 {
		return fmt.Errorf("attempted to switch an empty replace stack")
	}
	top := &r.stack[len(r.stack)-1]
	if top.inWith {
		return fmt.Errorf("replace block already has a replacement section")
	}
	top.inWith = true
	return nil
}

// pop closes the top block, throwing an error if the stack is empty or
// the block never reached its replacement section.
func (r *replaceStack) pop() error {
	if len(r.stack) == 0 {
		return fmt.Errorf("attempted to pop an empty replace stack")
	}
	if !r.stack[len(r.stack)-1].inWith {
		return fmt.Errorf("replace block has no replacement section")
	}
	r.stack = r.stack[:len(r.stack)-1]
	return nil
}

// drop reports whether the current line should be dropped. The original
// section is dropped when the directive fires, and the replacement section
// is dropped when it doesn't.
func (r *replaceStack) drop() bool {
	if len(r.stack) == 0 {
		return false
	}
	top := r.stack[len(r.stack)-1]
	return top.dropped || top.fired != top.inWith
}

// size gets the current size of the stack.
func (r *replaceStack) size() int {
	return len(r.stack)
}
