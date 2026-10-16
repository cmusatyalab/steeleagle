package listener

// Used by the authentication interceptor to map process IDs
// to named modules in the system; these codes are then checked
// within the law file for permissions (e.g. the mission module
// calling Hold would map to mission.Hold)
type AuthCode int

const (
	ServerCode AuthCode = iota
	AdminCode
	MissionCode
	ExternalCode
	UnknownCode
)

// Converts an AuthCode to its string representation.
func (c AuthCode) String() string {
	switch c {
	case ServerCode:
		return "server"
	case AdminCode:
		return "admin"
	case MissionCode:
		return "mission"
	case ExternalCode:
		return "external"
	default:
		return "unknown"
	}
}
