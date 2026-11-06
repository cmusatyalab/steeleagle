#!/usr/bin/env python3
"""
netsim.py - simulate a fluctuating link on one port of one interface.

Every --interval seconds a bandwidth is drawn from a Weibull distribution and
mapped into the profile's [min, max] Kbps range. The rate is applied with tc.
When the drawn rate is 0 Kbps, the port is shut off completely.

Profiles (Kbps):
    normal        2000 - 3000
    limited        500 - 1000
    degraded        50 -  100
    intermittent     0 -  100
    denied           0 -    0
    malicious        intermittent, plus --failpoints

--direction ingress (default) shapes incoming traffic via an IFB redirect.
--direction egress shapes outgoing traffic directly on the interface, using
a second unthrottled class (ceiling --link-rate) for everything else on it.

Failpoints (malicious only) are (event_time, dead_time) pairs in seconds.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import re
import signal
import subprocess
import sys
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class Profile:
    min_kbps: int
    max_kbps: int
    shape: float
    scale: float


PROFILES: dict[str, Profile] = {
    "normal": Profile(2000, 3000, shape=2.0, scale=0.5),
    "limited": Profile(500, 1000, shape=2.0, scale=0.5),
    "degraded": Profile(50, 100, shape=2.0, scale=0.5),
    "intermittent": Profile(0, 100, shape=0.6, scale=0.25),
    "denied": Profile(0, 0, shape=1.0, scale=1.0),
}
PROFILES["malicious"] = PROFILES["intermittent"]

REDIRECT_PREFS = {"ip": 10, "ipv6": 11}
DROP_PREF = 1

L2_HEADER_BYTES = {"ether": 14, "loopback": 14}

L4_PROTO_NUMBERS = {"tcp": 6, "udp": 17}


def die(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


class Tc:
    def __init__(
        self,
        iface: str,
        ifb: str,
        port: int,
        dry_run: bool,
        direction: str = "ingress",
        link_rate: str = "10Gbit",
    ) -> None:
        self.iface = iface
        self.ifb = ifb
        self.port = port
        self.dry_run = dry_run
        self.direction = direction
        self.link_rate = link_rate
        self.port_off = False
        self.installed = False
        self.dropped_off_bytes = 0
        self.dropped_off_pkts = 0

    def run(self, *args: str, check: bool = True) -> subprocess.CompletedProcess | None:
        if self.dry_run:
            print("  $ " + " ".join(args))
            return None
        res = subprocess.run(args, capture_output=True, text=True)
        if check and res.returncode != 0:
            raise RuntimeError(
                f"command failed: {' '.join(args)}\n{res.stderr.strip()}"
            )
        return res

    def _port_filters(self, pref_map: dict[str, int], action: list[str]) -> None:
        for proto, pref in pref_map.items():
            if proto != "ip":
                continue
            for l4, l4num in L4_PROTO_NUMBERS.items():
                for side in ("sport", "dport"):
                    self.run(
                        "tc",
                        "filter",
                        "add",
                        "dev",
                        self.iface,
                        "ingress",
                        "protocol",
                        proto,
                        "pref",
                        str(pref),
                        "u32",
                        "match",
                        "ip",
                        "protocol",
                        str(l4num),
                        "0xff",
                        "match",
                        "ip",
                        side,
                        str(self.port),
                        "0xffff",
                        "action",
                        *action,
                    )

    def _port_filters_direct(self, pref_map: dict[str, int], classid: str) -> None:
        for proto, pref in pref_map.items():
            if proto != "ip":
                continue
            for l4, l4num in L4_PROTO_NUMBERS.items():
                for side in ("sport", "dport"):
                    self.run(
                        "tc",
                        "filter",
                        "add",
                        "dev",
                        self.iface,
                        "parent",
                        "1:",
                        "protocol",
                        proto,
                        "pref",
                        str(pref),
                        "u32",
                        "match",
                        "ip",
                        "protocol",
                        str(l4num),
                        "0xff",
                        "match",
                        "ip",
                        side,
                        str(self.port),
                        "0xffff",
                        "classid",
                        classid,
                    )

    def check_clean(self) -> None:
        if self.dry_run:
            return
        if self.direction == "ingress":
            out = self.run("tc", "qdisc", "show", "dev", self.iface).stdout
            if " clsact " in out or " ingress " in out:
                die(
                    f"{self.iface} already has an ingress/clsact qdisc. Refusing to replace it. "
                    f"If it is left over from this script, run with --cleanup."
                )
            if self.run("ip", "link", "show", self.ifb, check=False).returncode == 0:
                die(
                    f"interface {self.ifb} already exists. Run with --cleanup, or pick another --ifb."
                )
        else:
            out = self.run("tc", "qdisc", "show", "dev", self.iface).stdout
            if "htb 1:" in out:
                die(
                    f"{self.iface} already has this script's egress htb root qdisc. "
                    f"If it is left over from a crashed run, use --cleanup."
                )

    def setup(self, initial_kbps: int) -> None:
        self.installed = True
        if self.direction == "ingress":
            self.run("ip", "link", "add", self.ifb, "type", "ifb")
            self.run("ip", "link", "set", self.ifb, "up")
            self.run(
                "tc",
                "qdisc",
                "add",
                "dev",
                self.ifb,
                "root",
                "handle",
                "1:",
                "htb",
                "default",
                "1",
            )
            self.run(
                "tc",
                "class",
                "add",
                "dev",
                self.ifb,
                "parent",
                "1:",
                "classid",
                "1:1",
                "htb",
                *self._rate_args(initial_kbps),
            )
            self.run("tc", "qdisc", "add", "dev", self.iface, "clsact")
            self._port_filters(
                REDIRECT_PREFS, ["mirred", "egress", "redirect", "dev", self.ifb]
            )
        else:
            self.run(
                "tc",
                "qdisc",
                "add",
                "dev",
                self.iface,
                "root",
                "handle",
                "1:",
                "htb",
                "default",
                "2",
            )
            self.run(
                "tc",
                "class",
                "add",
                "dev",
                self.iface,
                "parent",
                "1:",
                "classid",
                "1:1",
                "htb",
                *self._rate_args(initial_kbps),
            )
            self.run(
                "tc",
                "class",
                "add",
                "dev",
                self.iface,
                "parent",
                "1:",
                "classid",
                "1:2",
                "htb",
                "rate",
                self.link_rate,
                "ceil",
                self.link_rate,
            )
            self._port_filters_direct(REDIRECT_PREFS, "1:1")

    @staticmethod
    def _rate_args(kbps: int) -> list[str]:
        bps = kbps_to_bps(kbps)
        return ["rate", f"{bps}bit", "ceil", f"{bps}bit", "quantum", "1514"]

    def set_rate(self, kbps: int) -> None:
        target = self.ifb if self.direction == "ingress" else self.iface
        self.run(
            "tc",
            "class",
            "change",
            "dev",
            target,
            "parent",
            "1:",
            "classid",
            "1:1",
            "htb",
            *self._rate_args(kbps),
        )

    def _iptables_rule_args(self, l4: str, side: str) -> list[str]:
        port_flag = "--sport" if side == "sport" else "--dport"
        return ["-p", l4, port_flag, str(self.port), "-j", "DROP"]

    def _iptables_drop_sent(self) -> tuple[int, int]:
        # tc has no loadable drop action on this kernel (act_gact is missing,
        # same as cls_flower), so the egress "off" state is a real netfilter
        # DROP rule instead of a tc filter+action. Byte/packet accounting for
        # it comes from `iptables -v` counters, not tc's filter stats.
        if self.dry_run:
            return 0, 0
        res = self.run("iptables", "-L", "OUTPUT", "-v", "-n", "-x", check=False)
        b = p = 0
        for line in res.stdout.splitlines():
            if "DROP" not in line:
                continue
            if f"dpt:{self.port}" not in line and f"spt:{self.port}" not in line:
                continue
            parts = line.split()
            try:
                p += int(parts[0])
                b += int(parts[1])
            except (IndexError, ValueError):
                continue
        return b, p

    def port_down(self) -> None:
        if not self.port_off:
            if self.direction == "ingress":
                self.run(
                    "tc",
                    "filter",
                    "add",
                    "dev",
                    self.ifb,
                    "parent",
                    "1:",
                    "protocol",
                    "all",
                    "pref",
                    str(DROP_PREF),
                    "matchall",
                    "action",
                    "drop",
                )
            else:
                for l4 in ("tcp", "udp"):
                    for side in ("sport", "dport"):
                        self.run(
                            "iptables",
                            "-A",
                            "OUTPUT",
                            *self._iptables_rule_args(l4, side),
                        )
            self.port_off = True

    def port_up(self) -> None:
        if self.port_off:
            if self.direction == "ingress":
                b, p = self._drop_filter_sent()
            else:
                b, p = self._iptables_drop_sent()
            self.dropped_off_bytes += b
            self.dropped_off_pkts += p
            if self.direction == "ingress":
                self.run(
                    "tc",
                    "filter",
                    "del",
                    "dev",
                    self.ifb,
                    "parent",
                    "1:",
                    "pref",
                    str(DROP_PREF),
                )
            else:
                for l4 in ("tcp", "udp"):
                    for side in ("sport", "dport"):
                        self.run(
                            "iptables",
                            "-D",
                            "OUTPUT",
                            *self._iptables_rule_args(l4, side),
                        )
            self.port_off = False

    def l2_header_bytes(self) -> int:
        res = (
            self.run("ip", "-j", "link", "show", "dev", self.iface, check=False)
            if not self.dry_run
            else None
        )
        try:
            link_type = json.loads(res.stdout)[0]["link_type"]
        except (AttributeError, ValueError, LookupError, TypeError):
            return 14
        return L2_HEADER_BYTES.get(link_type, 0)

    @staticmethod
    def _sum_sent(text: str) -> tuple[int, int]:
        b = p = 0
        for m in re.finditer(r"Sent (\d+) bytes (\d+) pkt", text):
            b += int(m.group(1))
            p += int(m.group(2))
        return b, p

    def _drop_filter_sent(self) -> tuple[int, int]:
        if self.dry_run:
            return 0, 0
        target = self.ifb if self.direction == "ingress" else self.iface
        res = self.run(
            "tc",
            "-s",
            "filter",
            "show",
            "dev",
            target,
            "parent",
            "1:",
            "pref",
            str(DROP_PREF),
            check=False,
        )
        return self._sum_sent(res.stdout)

    def stats(self) -> dict[str, int]:
        if self.dry_run:
            return {}
        if self.direction == "ingress":
            out = self.run(
                "tc", "-s", "qdisc", "show", "dev", self.ifb, "root", check=False
            ).stdout
        else:
            out = self.run(
                "tc", "-s", "class", "show", "dev", self.iface, check=False
            ).stdout
        m = re.search(r"Sent (\d+) bytes (\d+) pkt \(dropped (\d+)", out)
        delivered_b, delivered_p, qdisc_drop_p = (
            (int(x) for x in m.groups()) if m else (0, 0, 0)
        )
        off_b, off_p = self.dropped_off_bytes, self.dropped_off_pkts
        if self.port_off:
            b, p = self._drop_filter_sent()
            off_b += b
            off_p += p
        return {
            "delivered_bytes": delivered_b,
            "delivered_pkts": delivered_p,
            "off_dropped_bytes": off_b,
            "off_dropped_pkts": off_p,
            "queue_dropped_pkts": max(0, qdisc_drop_p - off_p),
        }

    def teardown(self) -> None:
        if self.direction == "ingress":
            self.run("tc", "qdisc", "del", "dev", self.iface, "clsact", check=False)
            self.run("ip", "link", "del", self.ifb, check=False)
        else:
            self.run("tc", "qdisc", "del", "dev", self.iface, "root", check=False)
            # In case a crashed run left a DROP rule installed (port_down()
            # without a matching port_up()), clear it so the port isn't left
            # silently blocked after this process exits.
            for l4 in ("tcp", "udp"):
                for side in ("sport", "dport"):
                    self.run(
                        "iptables",
                        "-D",
                        "OUTPUT",
                        *self._iptables_rule_args(l4, side),
                        check=False,
                    )
        self.port_off = False


def parse_failpoints(text: str) -> list[tuple[float, float]]:
    text = text.strip()
    if not text:
        return []
    try:
        if text.startswith("["):
            pairs = [(float(a), float(b)) for a, b in json.loads(text)]
        else:
            pairs = []
            for item in text.split(","):
                a, b = item.split(":")
                pairs.append((float(a), float(b)))
    except (ValueError, TypeError, json.JSONDecodeError) as e:
        raise argparse.ArgumentTypeError(
            f"bad failpoints {text!r} ({e}); use '30:10,90:5' or '[[30,10],[90,5]]'"
        )
    for event, dead in pairs:
        if event < 0 or dead <= 0:
            raise argparse.ArgumentTypeError(
                f"failpoint ({event}, {dead}): event time must be >= 0 and dead time > 0"
            )
    return pairs


def merge_windows(failpoints: list[tuple[float, float]]) -> list[tuple[float, float]]:
    windows: list[list[float]] = []
    for start, end in sorted((e, e + d) for e, d in failpoints):
        if windows and start <= windows[-1][1]:
            windows[-1][1] = max(windows[-1][1], end)
        else:
            windows.append([start, end])
    return [(s, e) for s, e in windows]


def kbps_to_bps(kbps: float) -> int:
    return round(kbps * 1000)


def human_bytes(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1000 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.2f} {unit}"
        n /= 1000
    return ""


def print_summary(
    tc: Tc, port: int, elapsed: float, l2_header: int | None = None
) -> None:
    if not tc.installed:
        return
    try:
        st = tc.stats()
    except Exception as e:
        print(f"could not read byte counters: {e}", file=sys.stderr)
        return
    if not st:
        return
    hdr = l2_header if l2_header is not None else tc.l2_header_bytes()

    def ip_bytes(wire: int, pkts: int) -> int:
        return max(0, wire - hdr * pkts)

    deliv = ip_bytes(st["delivered_bytes"], st["delivered_pkts"])
    off = ip_bytes(st["off_dropped_bytes"], st["off_dropped_pkts"])
    avg_kbps = deliv * 8 / 1000 / elapsed if elapsed > 0 else 0.0
    print(
        f"\n=== port {port} {tc.direction} totals over {elapsed:.1f} s "
        f"(IP-layer bytes: {hdr}-byte link header per packet removed) ==="
    )
    print(
        f"  delivered through shaper : {human_bytes(deliv):>11} ({deliv} bytes, "
        f"{st['delivered_pkts']} pkts), avg {avg_kbps:.1f} Kbps"
    )
    print(
        f"  dropped while port off   : {human_bytes(off):>11} ({off} bytes, "
        f"{st['off_dropped_pkts']} pkts)"
    )
    print(
        f"  dropped by shaper queue  : {st['queue_dropped_pkts']} pkts (size not recorded by tc)"
    )
    print(
        f"  total arrived on port    : {human_bytes(deliv + off):>11} ({deliv + off} bytes, "
        f"{st['delivered_pkts'] + st['off_dropped_pkts']} pkts) + the queue drops"
    )
    print(
        f"  with link headers (wire) : delivered {st['delivered_bytes']} bytes, "
        f"dropped while off {st['off_dropped_bytes']} bytes"
    )


def draw_kbps(rng: random.Random, p: Profile) -> int:
    frac = min(1.0, rng.weibullvariate(p.scale, p.shape))
    return round(p.min_kbps + (p.max_kbps - p.min_kbps) * frac)


def simulate(args: argparse.Namespace, tc: Tc) -> None:
    base = PROFILES[args.profile]
    profile = Profile(
        args.min_kbps if args.min_kbps is not None else base.min_kbps,
        args.max_kbps if args.max_kbps is not None else base.max_kbps,
        args.shape if args.shape is not None else base.shape,
        args.scale if args.scale is not None else base.scale,
    )
    if not 0 <= profile.min_kbps <= profile.max_kbps:
        die(f"need 0 <= min ({profile.min_kbps}) <= max ({profile.max_kbps}) Kbps")
    windows = merge_windows(args.failpoints or [])
    rng = random.Random(args.seed)
    duration = args.duration if args.duration is not None else math.inf

    log_file = open(args.log, "w", newline="") if args.log else None
    log = csv.writer(log_file) if log_file else None
    if log:
        log.writerow(["t_sec", "drawn_kbps", "applied_kbps", "state"])

    print(
        f"profile={args.profile} direction={args.direction} bounds=[{profile.min_kbps:g}, {profile.max_kbps:g}] Kbps "
        f"weibull(shape={profile.shape}, scale={profile.scale}) interval={args.interval}s "
        f"seed={args.seed}"
    )
    if windows:
        print(
            "failpoint windows (s): " + ", ".join(f"[{s:g}, {e:g})" for s, e in windows)
        )

    tc.check_clean()
    tc.setup(max(profile.max_kbps, 1))
    print(
        f"shaping {args.direction} on {args.interface} port {args.port}"
        + (f" via {tc.ifb}" if args.direction == "ingress" else "")
        + ". Ctrl-C to stop."
    )

    t0 = time.monotonic()
    next_draw = 0.0
    drawn = 0
    applied: int | None = None
    applied_state = ""

    try:
        while True:
            t = time.monotonic() - t0
            if t >= duration:
                break

            while next_draw <= t:
                drawn = draw_kbps(rng, profile)
                next_draw += args.interval

            in_window = next((w for w in windows if w[0] <= t < w[1]), None)
            if in_window:
                target, state = 0, "failpoint"
            elif drawn == 0:
                target, state = 0, "off"
            else:
                target, state = drawn, "on"

            if target != applied or state != applied_state:
                if target == 0:
                    tc.port_down()
                else:
                    tc.set_rate(target)
                    tc.port_up()
                applied, applied_state = target, state
                print(
                    f"[{t:8.2f}s] {state:9s} {target:5d} Kbps (drawn {drawn})",
                    flush=True,
                )
            if log:
                log.writerow([f"{t:.3f}", drawn, target, state])
                log_file.flush()

            wake = min(next_draw, duration)
            for s, e in windows:
                if s > t:
                    wake = min(wake, s)
                    break
                if e > t:
                    wake = min(wake, e)
                    break
            time.sleep(max(0.0, wake - (time.monotonic() - t0)))
    finally:
        t_end = time.monotonic() - t0
        if log_file:
            log_file.close()
        print_summary(tc, args.port, min(t_end, duration), args.l2_header_bytes)


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("-i", "--interface", required=True)
    ap.add_argument("-p", "--port", required=True, type=int)
    ap.add_argument("--profile", choices=sorted(PROFILES), default="normal")
    ap.add_argument("--direction", choices=["ingress", "egress"], default="ingress")
    ap.add_argument(
        "--link-rate",
        default="10Gbit",
        help="egress only: ceiling for all other traffic on the interface",
    )
    ap.add_argument(
        "--failpoints",
        type=parse_failpoints,
        action="extend",
        default=None,
        help="malicious only: '30:10,90:5' or '[[30,10],[90,5]]'",
    )
    ap.add_argument("--min-kbps", type=float, default=None)
    ap.add_argument("--max-kbps", type=float, default=None)
    ap.add_argument("--interval", type=float, default=1.0)
    ap.add_argument("--duration", type=float, default=None)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--shape", type=float, default=None)
    ap.add_argument("--scale", type=float, default=None)
    ap.add_argument("--l2-header-bytes", type=int, default=None)
    ap.add_argument("--log", default=None)
    ap.add_argument("--ifb", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--cleanup", action="store_true")
    args = ap.parse_args()

    if not 1 <= args.port <= 65535:
        die("port must be in 1-65535")
    if args.interval <= 0:
        die("--interval must be > 0")
    if (args.shape is not None and args.shape <= 0) or (
        args.scale is not None and args.scale <= 0
    ):
        die("--shape and --scale must be > 0")
    if args.failpoints and args.profile != "malicious":
        die("--failpoints only applies to --profile malicious")
    if args.profile == "malicious" and not args.failpoints:
        print(
            "warning: malicious profile with no --failpoints behaves like intermittent",
            file=sys.stderr,
        )

    ifb = args.ifb or f"ifbsim{args.port}"
    if len(ifb) > 15:
        die(f"IFB name {ifb!r} is longer than 15 characters")
    tc = Tc(
        args.interface,
        ifb,
        args.port,
        args.dry_run,
        direction=args.direction,
        link_rate=args.link_rate,
    )

    if not args.dry_run:
        if os.geteuid() != 0:
            die("must be run as root (try sudo)")
        if subprocess.run(
            ["ip", "link", "show", args.interface], capture_output=True
        ).returncode:
            die(f"interface {args.interface!r} does not exist")

    if args.cleanup:
        tc.teardown()
        print(
            f"removed tc state on {args.interface}"
            + (f" and {ifb}" if args.direction == "ingress" else "")
        )
        return

    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, lambda s, _f: sys.exit(128 + s))

    try:
        simulate(args, tc)
    except KeyboardInterrupt:
        print()
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if tc.installed:
            tc.teardown()
            print(
                f"cleaned up: removed tc state on {args.interface}"
                + (f" and {ifb}" if args.direction == "ingress" else "")
            )


if __name__ == "__main__":
    main()
