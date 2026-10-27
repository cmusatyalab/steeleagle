package listener

// Used by the authentication interceptor to map process IDs
// to privilege levels within the system. Admin is always
// accepted, privileged allows high-level access, user allows
// temporary access, and external has no write permissions.
type AuthCode int

const (
	AdminCode AuthCode = iota
	PrivilegedCode
	UserCode
	ExternalCode
	UnknownCode
)

// Converts an AuthCode to its string representation.
func (c AuthCode) String() string {
	switch c {
	case AdminCode:
		return "admin"
	case PrivilegedCode:
		return "privileged"
	case UserCode:
		return "user"
	case ExternalCode:
		return "external"
	default:
		return "unknown"
	}
}

// Converts a string AuthCode to its AuthCode representation.
func ToCode(c string) AuthCode {
	switch c {
	case "admin":
		return AdminCode
	case "privileged":
		return PrivilegedCode
	case "user":
		return UserCode
	case "external":
		return ExternalCode
	default:
		return UnknownCode
	}
}
