package listener

import (
	"fmt"
	"net"
	"strings"
	"sync"

	"github.com/shirou/gopsutil/v3/process"
)

// aclNet is an IP range in an Acl and the AuthCode granted to it.
type aclNet struct {
	ipnet *net.IPNet
	code  AuthCode
}

// Acl provides a basic access control list for a listener. It maps process
// clients (by PID) and network clients (by IP CIDR) to the AuthCode they are
// granted. Clients not on the list are denied if the Acl is closed, or granted
// ExternalCode if it is open.
type Acl struct {
	nets []aclNet
	pids map[int]AuthCode
	open bool
	mu   sync.Mutex
}

// NewAcl constructs an Acl from maps of CIDR strings and allowed process IDs to
// the AuthCode granted to each. Plain IP addresses without a prefix length are
// treated as /32 (IPv4) or /128 (IPv6). Invalid CIDRs and PIDs are ignored. If
// open is set, clients not on the list are granted ExternalCode instead of
// being denied.
func NewAcl(cidrs map[string]AuthCode, pids map[int]AuthCode, open bool) *Acl {
	a := &Acl{pids: make(map[int]AuthCode, len(pids)), open: open}
	for cidr, code := range cidrs {
		a.AddIp(cidr, code)
	}
	for pid, code := range pids {
		a.AddPid(pid, code)
	}
	return a
}

// AllowsIp reports whether the given IP address is permitted by the ACL, and
// the AuthCode granted to it. If several CIDRs contain the IP, the most
// specific one wins.
func (a *Acl) AllowsIp(ip net.IP) (bool, AuthCode) {
	a.mu.Lock()
	defer a.mu.Unlock()
	best := -1
	code := UnknownCode
	for _, n := range a.nets {
		if !n.ipnet.Contains(ip) {
			continue
		}
		if ones, _ := n.ipnet.Mask.Size(); ones > best {
			best = ones
			code = n.code
		}
	}
	if best >= 0 {
		return true, code
	}
	return a.unlisted()
}

// AllowsPid reports whether pid is, or is a descendant of, any PID in the ACL,
// and the AuthCode granted to it. If several PIDs are ancestors of pid, the
// nearest one wins.
func (a *Acl) AllowsPid(pid int) (bool, AuthCode) {
	a.mu.Lock()
	defer a.mu.Unlock()
	if len(a.pids) > 0 {
		if code, ok := a.lookupPid(int32(pid)); ok {
			return true, code
		}
	}
	return a.unlisted()
}

// AllowsUnlisted reports whether a client that can't be identified by IP or
// PID is permitted by the ACL, and the AuthCode granted to it.
func (a *Acl) AllowsUnlisted() (bool, AuthCode) {
	a.mu.Lock()
	defer a.mu.Unlock()
	return a.unlisted()
}

// AddIp parses a CIDR and adds it to the ACL with the given AuthCode.
func (a *Acl) AddIp(cidr string, code AuthCode) error {
	a.mu.Lock()
	defer a.mu.Unlock()
	ipnet, err := parseCIDR(cidr)
	if err != nil {
		return err
	}
	a.nets = append(a.nets, aclNet{ipnet: ipnet, code: code})
	return nil
}

// AddPid adds an allowed PID to the ACL with the given AuthCode.
func (a *Acl) AddPid(pid int, code AuthCode) error {
	a.mu.Lock()
	defer a.mu.Unlock()
	if pid <= 0 {
		return fmt.Errorf("cannot add pid with value less than 0!")
	}
	a.pids[pid] = code
	return nil
}

// RemovePid removes a PID from the ACL, if it is present.
func (a *Acl) RemovePid(pid int) {
	a.mu.Lock()
	defer a.mu.Unlock()
	delete(a.pids, pid)
}

// ClearPids removes every PID from the ACL, leaving IP ranges untouched.
func (a *Acl) ClearPids() {
	a.mu.Lock()
	defer a.mu.Unlock()
	clear(a.pids)
}

// unlisted returns the decision for a client not on the ACL. The caller must
// hold the lock.
func (a *Acl) unlisted() (bool, AuthCode) {
	if a.open {
		return true, ExternalCode
	}
	return false, UnknownCode
}

// lookupPid walks upward from pid through its parent PIDs and returns the
// AuthCode of the first one on the ACL, stopping at PID 1 or on an error. The
// caller must hold the lock.
func (a *Acl) lookupPid(pid int32) (AuthCode, bool) {
	visited := make(map[int32]bool)
	current := pid
	for current > 1 && !visited[current] {
		if code, ok := a.pids[int(current)]; ok {
			return code, true
		}
		visited[current] = true
		ppid, err := parentOf(current)
		if err != nil {
			return UnknownCode, false
		}
		current = ppid
	}
	return UnknownCode, false
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

// parentOf returns the PPID of pid using gops
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
