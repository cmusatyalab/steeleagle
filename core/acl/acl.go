package acl

type ACLID string

const (
    Driver   ACLID = "driver"
    Mission  ACLID = "mission"
    Internal ACLID = "internal"
    Server   ACLID = "server"
    Engine   ACLID = "engine"
    External ACLID = "external"
)
