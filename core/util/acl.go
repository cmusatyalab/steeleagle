package util

import (
	"fmt"
	"net"
	"strings"
	"sync"

	"github.com/shirou/gopsutil/v3/process"
)

// ACL provides a basic access control list for a listener. It can be set to
// check access rights for process clients using PIDs or network clients using
// IP CIDRs.
type ACL struct {
	nets  []*net.IPNet
	cidrs []string
	pids  []int
	mu    sync.Mutex
}

// GetACL constructs an ACL from a list of CIDR strings and allowed process IDs.
// Plain IP addresses without a prefix length are treated as /32 (IPv4) or /128 (IPv6).
func GetACL(cidrs []string, pids []int) *ACL {
	nets := make([]*net.IPNet, 0, len(cidrs))
	for _, cidr := range cidrs {
		ipnet, err := parseCIDR(cidr)
		if err != nil {
			continue
		}
		nets = append(nets, ipnet)
	}
	return &ACL{nets: nets, cidrs: cidrs, pids: pids}
}

// AllowsIP reports whether the given IP address is permitted by the ACL.
func (a *ACL) AllowsIP(ip net.IP) bool {
	a.mu.Lock()
	defer a.mu.Unlock()
	for _, n := range a.nets {
		if n.Contains(ip) {
			return true
		}
	}
	return false
}

// AllowsPID reports whether pid is a descendant of any PID in the ACL's allowed list.
func (a *ACL) AllowsPID(pid int) bool {
	a.mu.Lock()
	defer a.mu.Unlock()
	for _, p := range a.pids {
		if ok, err := isPIDDescendant(int32(p), int32(pid)); err == nil && ok {
			return true
		}
	}
	return false
}

// AddIP parses a CIDR and adds it to the ACL.
func (a *ACL) AddIP(cidr string) error {
	a.mu.Lock()
	defer a.mu.Unlock()
	ipnet, err := parseCIDR(cidr)
	if err != nil {
		return err
	}
	a.nets = append(a.nets, ipnet)
	a.cidrs = append(a.cidrs, cidr)
	return nil
}

// AddPID adds an allowed PID to the ACL.
func (a *ACL) AddPID(pid int) error {
	a.mu.Lock()
	defer a.mu.Unlock()
    if pid <= 0 {
        return fmt.Errorf("cannot add pid with value less than 0!")
    }
	a.pids = append(a.pids, pid)
    return nil
}

// parseCIDR parses a CIDR string into a net.IPNet for easier checking.
func parseCIDR(cidr string) (*net.IPNet, error) {
	if !strings.Contains(cidr, "/") {
		ip := net.ParseIP(cidr)
		if ip == nil {
			return nil, fmt.Errorf("cidr couldn't be parsed: %s", cidr)
		}
		if ip.To4() != nil {
			cidr += "/32"
		} else {
			cidr += "/128"
		}
	}
	_, ipnet, err := net.ParseCIDR(cidr)
	return ipnet, err
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
