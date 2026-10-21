package policy

import _ "embed"

//go:embed defaults/check.rego
var DefaultRego string // DefaultRego is the default Rego OPA config for law interceptors.
