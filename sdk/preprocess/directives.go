package preprocess

// Directive is a pre-processor directive for overlay.go.
type Directive string

// Directives for the pre-processor. An -ifndef directive fires if any of
// its comma-separated types is undefined, and its -ifallndef clone only if
// all of them are.
const (
	DirectiveExclude         Directive = "// #exclude-ifndef"          // excludes next line
	DirectiveExcludeAll      Directive = "// #exclude-ifallndef"       // excludes next line
	DirectivePrivate         Directive = "// #private-ifndef"          // privates next line
	DirectivePrivateAll      Directive = "// #private-ifallndef"       // privates next line
	DirectiveBeginExclude    Directive = "// #begin-exclude-ifndef"    // starts exclude block
	DirectiveBeginExcludeAll Directive = "// #begin-exclude-ifallndef" // starts exclude block
	DirectiveEndExclude      Directive = "// #end-exclude"             // ends exclude block
	DirectiveBeginPrivate    Directive = "// #begin-private-ifndef"    // starts private block
	DirectiveBeginPrivateAll Directive = "// #begin-private-ifallndef" // starts private block
	DirectiveEndPrivate      Directive = "// #end-private"             // ends private block
	DirectiveBeginReplace    Directive = "// #begin-replace-ifndef"    // starts replace block
	DirectiveBeginReplaceAll Directive = "// #begin-replace-ifallndef" // starts replace block
	DirectiveReplaceWith     Directive = "// #replace-with"            // starts with block for replace
	DirectiveEndReplace      Directive = "// #end-replace"             // ends replace block
	directiveNull            Directive = ""                            // null directive
)

// directives are every directive getTag recognizes.
var directives = []Directive{
	DirectiveExclude, DirectiveExcludeAll,
	DirectivePrivate, DirectivePrivateAll,
	DirectiveBeginExclude, DirectiveBeginExcludeAll, DirectiveEndExclude,
	DirectiveBeginPrivate, DirectiveBeginPrivateAll, DirectiveEndPrivate,
	DirectiveBeginReplace, DirectiveBeginReplaceAll, DirectiveReplaceWith, DirectiveEndReplace,
}

// allDirectives maps each -ifallndef directive to the -ifndef directive it
// clones.
var allDirectives = map[Directive]Directive{
	DirectiveExcludeAll:      DirectiveExclude,
	DirectivePrivateAll:      DirectivePrivate,
	DirectiveBeginExcludeAll: DirectiveBeginExclude,
	DirectiveBeginPrivateAll: DirectiveBeginPrivate,
	DirectiveBeginReplaceAll: DirectiveBeginReplace,
}
