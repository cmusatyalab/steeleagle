package preprocess

// Directive is a pre-processor directive for overlay.go.
type Directive string

// Base directives for overlay scrubbing.
const (
	DirectiveExclude      Directive = "// #exclude-ifndef"       // excludes next line
	DirectivePrivate      Directive = "// #private-ifndef"       // privates next line
	DirectiveBeginExclude Directive = "// #begin-exclude-ifndef" // starts exclude block
	DirectiveEndExclude   Directive = "// #end-exclude"          // ends exclude block
	DirectiveBeginPrivate Directive = "// #begin-private-ifndef" // starts private block
	DirectiveEndPrivate   Directive = "// #end-private"          // ends private block
	directiveNull         Directive = ""                         // null directive
)
