package events

// Comparator selects how a threshold-style event compares the current
// telemetry value against its configured Threshold.
type Comparator uint32

const (
	LessOrEqual    Comparator = iota // fires once the value drops to or below Threshold
	GreaterOrEqual                   // fires once the value rises to or above Threshold
)

// compareUint32 reports whether cur satisfies cmp against threshold.
func compareUint32(cur, threshold uint32, cmp Comparator) bool {
	switch cmp {
	case GreaterOrEqual:
		return cur >= threshold
	default: // LessOrEqual
		return cur <= threshold
	}
}
