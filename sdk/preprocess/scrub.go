package preprocess

import (
	"fmt"
	"strings"
)

// Scrub inspects a file source byte slice and removes or privates lines according
// to pre-processor directives.
func Scrub(filter func(string) bool, src []byte) ([]byte, bool, error) {
	lines := strings.Split(string(src), "\n")
	out := make([]string, len(lines))
	dirty := false // dirty tracks whether the file was modified or not
	// Track active private or remove blocks
	privateStack, excludeStack := blockStack{}, blockStack{}
	nextPrivate, nextExclude := false, false // designates a next-line exclude or private
	for i, line := range lines {
		tag, types := getTag(line)
		if tag != "" {
			out[i] = "" // directive lines are preprocessor syntax, not source, so scrub them too
			dirty = true
			satisfied := false
			for _, t := range types { // check whether the tag is satisfied by the cap file
				satisfied = satisfied || !filter(strings.TrimSpace(t))
			}
			switch tag {
			case DirectiveExclude:
				nextExclude = satisfied
			case DirectivePrivate:
				nextPrivate = satisfied
			case DirectiveBeginExclude:
				excludeStack.push(satisfied)
			case DirectiveEndExclude:
				if err := excludeStack.pop(); err != nil {
					return nil, false, &PreprocessError{error: fmt.Errorf("#end-exclude does not end block"), LineNo: uint32(i + 1)}
				}
			case DirectiveBeginPrivate:
				privateStack.push(satisfied)
			case DirectiveEndPrivate:
				if err := privateStack.pop(); err != nil {
					return nil, false, &PreprocessError{error: fmt.Errorf("#end-private does not end block"), LineNo: uint32(i + 1)}
				}
			}
		} else {
			// A next-line directive should govern the next non-comment line,
			// so comment lines (e.g. doc comments) in between are carried
			// along with whatever the directive does, and the directive
			// stays pending until a non-comment line is reached.
			comment := isCommentLine(line)
			// Exclude or private lines if inside a block or after a directive
			if nextExclude || excludeStack.top() {
				out[i] = ""
				dirty = true
				nextExclude = nextExclude && comment
			} else if nextPrivate || privateStack.top() {
				out[i] = privateLine(line)
				dirty = dirty || (out[i] != line) // only set dirty if we actually modified a line
				nextPrivate = nextPrivate && comment
			} else {
				out[i] = line
			}
		}
	}
	// Every new block added to the stack should be closed and thus these should
	// only contain the first false elements added
	if excludeStack.size() > 0 {
		return nil, false, &PreprocessError{error: fmt.Errorf("unenclosed exclude block found")}
	} else if privateStack.size() > 0 {
		return nil, false, &PreprocessError{error: fmt.Errorf("unenclosed private block found")}
	}
	return []byte(strings.Join(out, "\n")), dirty, nil
}

// getTag returns a directive if a line contains it, otherwise
// an empty string, along with the directive tagged types if
// applicable.
func getTag(line string) (Directive, []string) {
	trimmed := strings.TrimSpace(line)
	tag := directiveNull
	if strings.HasPrefix(trimmed, string(DirectiveExclude)) {
		tag = DirectiveExclude
	} else if strings.HasPrefix(trimmed, string(DirectivePrivate)) {
		tag = DirectivePrivate
	} else if strings.HasPrefix(trimmed, string(DirectiveBeginExclude)) {
		tag = DirectiveBeginExclude
	} else if strings.HasPrefix(trimmed, string(DirectiveEndExclude)) {
		tag = DirectiveEndExclude
	} else if strings.HasPrefix(trimmed, string(DirectiveBeginPrivate)) {
		tag = DirectiveBeginPrivate
	} else if strings.HasPrefix(trimmed, string(DirectiveEndPrivate)) {
		tag = DirectiveEndPrivate
	}
	return tag, strings.Split(trimmed[len(tag):], ",")
}

// isCommentLine reports whether a line is a Go line comment.
func isCommentLine(line string) bool {
	return strings.HasPrefix(strings.TrimSpace(line), "//")
}

// privateLine privates a line of Go by lowercasing the first
// character in the line.
func privateLine(line string) string {
	trimmed := strings.TrimLeft(line, " \t")
	indent := line[:len(line)-len(trimmed)]

	if trimmed == "" || trimmed[0] < 'A' || trimmed[0] > 'Z' {
		return line
	}
	return indent + strings.ToLower(trimmed[:1]) + trimmed[1:]
}
