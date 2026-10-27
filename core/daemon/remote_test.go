package daemon

import (
	"slices"
	"testing"
)

// TestRemotes checks the bookkeeping of child daemons: a registration
// replaces an earlier one from the same IP, which then can't remove the new
// one, and children are listed in order of their IPs.
func TestRemotes(t *testing.T) {
	d := newIdleDaemon(t, orchAddr, testConfig(t, "orch", ""))
	svc := func(names ...string) []*daemonService {
		var out []*daemonService
		for _, n := range names {
			out = append(out, &daemonService{name: n})
		}
		return out
	}

	b, err := d.addRemote("10.0.0.2", "b", 9000, svc("10.0.0.2.x"))
	if err != nil {
		t.Fatal(err)
	}
	old, err := d.addRemote("10.0.0.10", "c", 9000, svc("10.0.0.10.x", "10.0.0.10.y"))
	if err != nil {
		t.Fatal(err)
	}
	if d.remoteFor("10.0.0.10.y") != old || d.remoteFor("10.0.0.2.x") != b {
		t.Error("remoteFor() didn't find the children's services")
	}

	// The child re-registers before its old registration ends
	child, err := d.addRemote("10.0.0.10", "c", 9001, svc("10.0.0.10.z"))
	if err != nil {
		t.Fatal(err)
	}
	if d.remoteFor("10.0.0.10.y") != nil || d.remoteFor("10.0.0.10.z") != child {
		t.Error("services of the replaced registration are still routed")
	}
	if old.conn.GetState().String() != "SHUTDOWN" {
		t.Errorf("replaced connection is %v, want it closed", old.conn.GetState())
	}
	d.removeRemote(old)
	if d.remoteFor("10.0.0.10.z") != child {
		t.Error("ending the replaced registration removed the new one")
	}

	var ips []string
	for _, c := range d.listRemotes() {
		ips = append(ips, c.ip)
	}
	// Ordered as strings, which is all that matters for a stable listing
	if !slices.Equal(ips, []string{"10.0.0.10", "10.0.0.2"}) {
		t.Errorf("listRemotes() = %v, want both children in order", ips)
	}

	d.removeRemote(child)
	if d.remoteFor("10.0.0.10.z") != nil || len(d.listRemotes()) != 1 {
		t.Error("removed child is still listed")
	}
	d.closeRemotes()
	if len(d.listRemotes()) != 0 || d.remoteFor("10.0.0.2.x") != nil {
		t.Error("children are still listed after closing them all")
	}
	if b.conn.GetState().String() != "SHUTDOWN" {
		t.Errorf("connection is %v after closing all children, want it closed", b.conn.GetState())
	}
}
