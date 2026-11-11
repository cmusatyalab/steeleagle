# netsim

Simulates an unreliable incoming network link on a single port of a single
interface. Every `--interval` seconds it draws a bandwidth from a Weibull
distribution, scales it into the profile's range, and applies it with `tc`.
When the drawn bandwidth is 0 Kbps, the port is shut off completely until a
later draw gives a non-zero rate.

All rates are in **Kbps (kilobits per second)**. The script converts them to
bits per second itself before passing them to `tc`. (tc's own `kbps` unit means
kilo*bytes* per second, so the script avoids it.)

## Requirements

- Linux with `tc` and `ip` from iproute2, and the `ifb` kernel module
- Root (the script changes kernel network settings)
- Python 3.9+. Only the standard library is used, so there is nothing to install from PyPI.

## Profiles

| Profile        | Min Kbps | Max Kbps | Behaviour                                         |
|----------------|---------:|---------:|---------------------------------------------------|
| `normal`       |     2000 |     3000 |                                                   |
| `limited`      |      500 |     1000 |                                                   |
| `degraded`     |       50 |      100 |                                                   |
| `intermittent` |        0 |      100 | Drops to 0 (port off) on roughly 9% of draws      |
| `denied`       |        0 |        0 | Port is always off                                |
| `malicious`    |        0 |      100 | Intermittent, plus forced outages at `--failpoints` |
| `delay`        |        – |        – | Bandwidth unshaped; 0 – 300 ms of variable latency (see below) |

`--min-kbps` and `--max-kbps` override a profile's bounds:

```bash
sudo python3 netsim -i eth0 -p 5201 --profile limited --min-kbps 200 --max-kbps 800
```

### How bandwidth is drawn

Each draw is `min + (max - min) * clip(X, 0, 1)` with `X ~ Weibull(shape, scale)`,
rounded to a whole number of Kbps. A result of 0 shuts the port off.

| Profiles                         | shape | scale | Effect                                |
|----------------------------------|------:|------:|---------------------------------------|
| normal, limited, degraded        |   2.0 |   0.5 | Clusters around the middle of the range |
| intermittent, malicious          |   0.6 |  0.25 | Piles up near 0, so the port drops out |

`--shape` and `--scale` override these.

### Delay

The `delay` profile doesn't limit the bandwidth (the port's class runs at
`--link-rate`). Every `--interval` seconds it draws a one-way delay uniformly
from `[--min-delay-ms, --max-delay-ms]` (default 0 – 300), rounded to a whole
ms, and applies it with a netem qdisc under the port's class:

```bash
sudo python3 netsim -i eth0 -p 5201 --profile delay --max-delay-ms 150
```

Lowering the delay lets newly sent packets overtake ones still held under the
old delay, so TCP sees some reordering. The trace's kbps columns are empty,
and `delay_ms` holds the delay; its state is `delay`.

## Failpoints (malicious profile only)

A failpoint is an `event_time:dead_time` pair in seconds from the start of the
simulation. When the clock reaches `event_time`, the port is killed for
`dead_time` seconds no matter what the distribution says. Afterwards the
intermittent simulation takes over again.

There are three equivalent ways to give several failpoints:

```bash
# comma-separated
sudo python3 netsim -i eth0 -p 5201 --profile malicious --failpoints 30:10,90:5,150:20

# repeat the flag
sudo python3 netsim -i eth0 -p 5201 --profile malicious \
    --failpoints 30:10 --failpoints 90:5 --failpoints 150:20

# JSON list of pairs (quoted so the shell leaves the brackets alone)
sudo python3 netsim -i eth0 -p 5201 --profile malicious --failpoints '[[30,10],[90,5],[150,20]]'
```

Each of these kills the port from 30–40 s, 90–95 s and 150–170 s.

- **Order doesn't matter.** Failpoints are sorted.
- **Overlaps merge.** `30:10,35:10` becomes one outage from 30 to 45 s.
- **Decimals work**, e.g. `12.5:0.75`.
- **The final windows are printed at startup**, e.g. `failpoint windows (s): [30, 40), [90, 95), [150, 170)`.
- **Draws keep going during a failpoint.** With the same `--seed`, the
  underlying trace matches a plain `intermittent` run exactly.
- Using `--failpoints` with any other profile is an error. `malicious` without
  failpoints behaves like `intermittent` (with a warning).

## Options

| Option                  | Default            | Meaning                                                    |
|-------------------------|--------------------|------------------------------------------------------------|
| `-i, --interface`       | required           | Interface to shape                                         |
| `-p, --port`            | required           | Port to shape                                              |
| `--profile`             | `normal`           | One of the profiles above                                  |
| `--failpoints`          | none               | Malicious only; see above                                  |
| `--min-kbps`, `--max-kbps` | profile's bounds | Override the bandwidth range, in Kbps                      |
| `--min-delay-ms`, `--max-delay-ms` | `0`, `300` | Delay only: the range of the delay, in ms              |
| `--interval`            | `1.0`              | Seconds between draws                                      |
| `--duration`            | until Ctrl-C       | Stop after this many seconds                               |
| `--seed`                | random             | RNG seed for a reproducible trace                          |
| `--shape`, `--scale`    | profile's values   | Override the Weibull parameters                            |
| `--l2-header-bytes`     | auto               | Link header bytes to subtract per packet in the totals     |
| `--log PATH`            | off                | Write a CSV trace (`t_sec, drawn_kbps, applied_kbps, state, delay_ms`) |
| `--ifb NAME`            | `ifbsim<port>`     | Name of the virtual IFB device                             |
| `--dry-run`             | off                | Print the tc commands instead of running them (no root needed) |
| `--cleanup`             | off                | Remove leftover tc state from a crashed run and exit       |

## Output

While running, each change of rate or state is printed:

```
[    0.00s] on           24 Kbps (drawn 24)
[    1.00s] failpoint     0 Kbps (drawn 44)
[    1.50s] on          118 Kbps (drawn 118)
```

`state` is `on`, `off` (the distribution gave 0) or `failpoint` (or `delay`,
under the delay profile, which prints the delay instead).

When the run ends (duration reached, Ctrl-C, SIGTERM or SIGHUP), the script
prints how much data went through the port before cleaning up:

```
=== port 5201 ingress totals over 10.0 s (IP-layer bytes: 14-byte link header per packet removed) ===
  delivered through shaper :   150.00 KB (150000 bytes, 100 pkts), avg 120.0 Kbps
  dropped while port off   :    15.00 KB (15000 bytes, 10 pkts)
  dropped by shaper queue  : 3 pkts (size not recorded by tc)
  total arrived on port    :   165.00 KB (165000 bytes, 110 pkts) + the queue drops
  with link headers (wire) : delivered 151400 bytes, dropped while off 15140 bytes
```

- **Delivered** is what got through to the application.
- **Dropped while port off** is traffic discarded while the rate was 0 or a failpoint was active.
- **Dropped by shaper queue** is traffic that arrived faster than the current rate
  and overflowed the queue. tc only records a packet count for these.

### What the byte counts include

tc counts each packet as it appears on the wire, including the link-layer
header. The summary subtracts that header per packet to give IP-layer bytes:
14 bytes for Ethernet and loopback, 0 for L3 devices such as WireGuard or tun.
Override with `--l2-header-bytes`. The raw wire totals are on the last line.

- IP and TCP/UDP headers are still included (about 52 bytes per packet for TCP),
  so the data your application sees is somewhat lower than "delivered".
- The Kbps limit also counts the 14-byte link header, so measured IP-level
  throughput comes out slightly below the configured rate.
- The kernel often merges incoming packets into larger ones; the counters
  should count the original packets, so the per-packet subtraction stays
  correct. This is based on reading the kernel source and hasn't been measured yet.

## How it works

```
<iface>  clsact ingress
           pref 10/11  flower match on port  ->  redirect to IFB
<ifb>    root htb 1:, class 1:1  rate = ceil = current Kbps
           pref 1  matchall -> drop            (only while the port is off)
```

Under `delay`, the class runs at `--link-rate` and has a
`netem delay <ms>` qdisc (handle `10:`) under it, changed with
`tc qdisc change` each draw.

tc can't shape incoming traffic directly, so packets for the port are
redirected to a virtual IFB device and shaped there. Rate changes use
`tc class change`. HTB can't run at 0, so "off" adds a drop filter on the IFB
and "on" sets the new rate and then removes it.

"Traffic on the port" means TCP or UDP, IPv4 or IPv6, with the port as either
the destination port (you are the server) or the source port (you are a client
of a remote service on that port).

## Safety and cleanup

- The script refuses to start if the interface already has an ingress or clsact
  qdisc, or if the IFB device already exists, so it won't overwrite other setups.
- It removes everything it added on normal exit, Ctrl-C, SIGTERM and SIGHUP.
- After a `kill -9` or crash, run:

  ```bash
  sudo python3 netsim -i eth0 -p 5201 --cleanup
  ```

  This deletes the clsact qdisc on the interface and the IFB device. Don't run it
  if something else on the machine is using a clsact qdisc on that interface.

## Quick test

On the shaped machine:

```bash
sudo python3 netsim -i eth0 -p 5201 --profile malicious --failpoints 5:5 --duration 15 --log trace.csv
```

From the same machine, pull data from an `iperf3 -s` server on another host,
so the traffic arrives on port 5201:

```bash
iperf3 -c <server> -p 5201 -R -t 15
```

Compare iperf3's received total with the "delivered" line.
