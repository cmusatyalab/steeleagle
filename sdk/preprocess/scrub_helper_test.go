package preprocess_test

import (
	"strings"
	"testing"

	"github.com/cmusatyalab/steeleagle/sdk"
)

// newCapFile builds a *sdk.CapFile whose unsupported set is exactly
// unsupported, for use as Scrub's capability lookup in tests. Since
// types are looked up as a merged set, all types are used as Fields for
// simplicity.
func newCapFile(t *testing.T, unsupported ...string) *sdk.CapFile {
	t.Helper()
	var sb strings.Builder
	sb.WriteString("[unsupported]\nfields = [")
	for i, f := range unsupported {
		if i > 0 {
			sb.WriteString(", ")
		}
		sb.WriteString(`"` + f + `"`)
	}
	sb.WriteString("]\n")
	cap, err := sdk.ParseCapFromBytes([]byte(sb.String()))
	if err != nil {
		t.Fatalf("failed to parse test cap file: %v", err)
	}
	return cap
}
