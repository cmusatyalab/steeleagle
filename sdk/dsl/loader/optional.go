package loader

import (
	"regexp"
	"strings"
)

// optionalTag matches a "#optional" or "#optional[<value>]" doc-comment
// directive, capturing <value> (the group is empty when there's no bracket).
var optionalTag = regexp.MustCompile(`#optional(?:\[([^\]]*)\])?`)

// extractOptional scrubs a "#optional" or "#optional[<value>]" directive
// out of doc, reporting whether one was present and, if it carried a
// bracketed default, its <value>.
func extractOptional(doc string) (scrubbed string, optional bool, value string) {
	loc := optionalTag.FindStringSubmatchIndex(doc)
	if loc == nil {
		return doc, false, ""
	}
	if loc[2] >= 0 {
		value = doc[loc[2]:loc[3]]
	}
	return strings.TrimSpace(doc[:loc[0]] + doc[loc[1]:]), true, value
}
