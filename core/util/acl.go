package util

import (
	"net"
	"strings"
    "slices"

	"github.com/rs/zerolog/log"
)

type ACL struct {
	nets []*net.IPNet
    pids []int
}

func GetACL(cidrs []string, pids []int) *ACL {
	nets := make([]*net.IPNet, 0, len(cidrs))
	for _, cidr := range cidrs {
		if !strings.Contains(cidr, "/") {
			ip := net.ParseIP(cidr)
			if ip == nil {
				log.Warn().Str("ip", cidr).Msg("couldn't parse ip, ignoring")
				continue
			}
			if ip.To4() != nil {
				cidr += "/32"
			} else {
				cidr += "/128"
			}
		}
		_, ipnet, err := net.ParseCIDR(cidr)
		if err != nil {
			log.Warn().Err(err).Str("cidr", cidr).Msg("couldn't parse cidr, ignoring")
			continue
		}
		nets = append(nets, ipnet)
	}
    return &ACL{nets: nets, pids: pids}
}

func (a *ACL) AllowsIP(ip net.IP) bool {
	for _, n := range a.nets {
		if n.Contains(ip) {
			return true
		}
	}
	return false
}

func (a *ACL) AllowsPID(pid int) bool {
    return slices.Contains(a.pids, pid)
}
