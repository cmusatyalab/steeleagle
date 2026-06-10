package util

import (
	"net"
	"strings"
    "fmt"

	"github.com/rs/zerolog/log"
    "github.com/shirou/gopsutil/v3/process"
)

type ACL struct {
	nets  []*net.IPNet
    cidrs []string
    pids  []int
}

// GetACL constructs an ACL from a list of CIDR strings and allowed process IDs.
// Plain IP addresses without a prefix length are treated as /32 (IPv4) or /128 (IPv6).
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
    return &ACL{nets: nets, cidrs: cidrs, pids: pids}
}

// AllowsIP reports whether the given IP address is permitted by the ACL.
func (a *ACL) AllowsIP(ip net.IP) bool {
	for _, n := range a.nets {
		if n.Contains(ip) {
            log.Debug().Str("ip", ip.String()).Strs("allowed", a.cidrs).Msg("ip accepted")
			return true
		}
	}
    log.Debug().Str("ip", ip.String()).Strs("allowed", a.cidrs).Msg("ip rejected")
	return false
}

// AllowsPID reports whether pid is a descendant of any PID in the ACL's allowed list.
func (a *ACL) AllowsPID(pid int) bool {
    var err error
    for _, p := range a.pids {
        if ok, err := isPIDDescendant(int32(p), int32(pid)); err == nil && ok {
            log.Debug().Int("pid", pid).Ints("allowed", a.pids).Msg("pid accepted")
            return true
        }
        if err != nil {
            log.Debug().Err(err).Int("ppid", p).Int("pid", pid).Msg("pid heritage could not be validated")
        }
    }
    log.Debug().Int("pid", pid).Ints("allowed", a.pids).Msg("pid rejected")
    return false
}

// parentOf returns the PPID of pid using gopsutil.
func parentOf(pid int32) (int32, error) {
	p, err := process.NewProcess(pid)
	if err != nil {
		return -1, fmt.Errorf("process %d not found: %w", pid, err)
	}
	ppid, err := p.Ppid()
	if err != nil {
		return -1, fmt.Errorf("could not get ppid of %d: %w", pid, err)
	}
	return ppid, nil
}

// isPIDDescendant reports whether target is a descendant of ancestor.
// It walks upward through parent PIDs until it finds ancestor (true)
// or reaches PID 1 / an error (false).
func isPIDDescendant(ancestor, target int32) (bool, error) {
	visited := make(map[int32]bool)

    // Vacuously true if pids are equal
    if ancestor == target {
        return true, nil
    }

	current := target
	for {
		ppid, err := parentOf(current)
		if err != nil {
			return false, err
		}

		if ppid == ancestor {
			return true, nil
		}
		if ppid <= 1 {
			return false, nil
		}
		if visited[ppid] {
			return false, fmt.Errorf("cycle detected in process tree at pid %d", ppid)
		}
		visited[ppid] = true
		current = ppid
	}
}
