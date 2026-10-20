package preprocess_test

import (
	"strings"
	"testing"

	"github.com/cmusatyalab/steeleagle/config"
)

// newDriverCap builds a *config.DriverCap whose unsupported set is exactly
// unsupported, for use as Scrub's capability lookup in tests. Since
// types are looked up as a merged set, all types are used as Fields for
// simplicity.
func newDriverCap(t *testing.T, unsupported ...string) *config.DriverCap {
	t.Helper()
	var sb strings.Builder
	sb.WriteString("[driver.unsupported]\nfields = [")
	for i, f := range unsupported {
		if i > 0 {
			sb.WriteString(", ")
		}
		sb.WriteString(`"` + f + `"`)
	}
	sb.WriteString("]\n")
	plugin, err := config.ParsePluginConfigFromBytes([]byte(sb.String()))
	if err != nil {
		t.Fatalf("failed to parse test cap file: %v", err)
	}
	return plugin.Driver
}
