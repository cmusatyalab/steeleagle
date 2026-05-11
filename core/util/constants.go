package util

// Used by the authentication interceptor to map process IDs
// to named modules in the system; these codes are then checked
// within the law file for permissions (e.g. the mission module
// calling Hold would map to mission.Hold)
type AuthCode string

const (
	ServerCode   authCode = "server"
	AdminCode    authCode = "admin"
	MissionCode  authCode = "mission"
	ExternalCode authCode = "external"
	UnknownCode  authCode = "unknown"
)
