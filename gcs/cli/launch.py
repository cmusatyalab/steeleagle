#!/usr/bin/env python3
import argparse
import subprocess
import sys


def run_module(module: str, args: list[str]):
    return subprocess.Popen(
        ["uv", "run", module, *args],
        stdin=sys.stdin,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )


def main():
    p = argparse.ArgumentParser(description="Launch local CLI + viewer for multiple drones")
    p.add_argument(
        "-c",
        "--config",
        default=None,
        help="Path to TOML config file with drone definitions. "
             "Example: -c drones.toml",
    )
    p.add_argument(
        "-a",
        "--addrs",
        nargs="+",
        default=None,
        help="gRPC kernel addresses for local_cli.py (alternative to config). "
             "Format: 'name=address' or just 'address'. "
             "Examples: -a drone1=unix:///tmp/kernel1.sock drone2=unix:///tmp/kernel2.sock",
    )
    p.add_argument(
        "-i",
        "--imagery-addrs",
        nargs="+",
        default=None,
        help="ZMQ imagery addresses for view.py (alternative to config). "
             "Format: 'name=address' or just 'address'. "
             "Examples: -i drone1=ipc:///tmp/imagery1.sock drone2=ipc:///tmp/imagery2.sock",
    )
    p.add_argument(
        "--rgb",
        action="store_true",
        help="Tell view.py to treat frames as RGB and convert to BGR",
    )
    args = p.parse_args()

    # Build arguments for local_cli.py
    cli_args = []
    if args.config:
        cli_args.extend(["-c", args.config])
    elif args.addrs:
        cli_args.append("-a")
        cli_args.extend(args.addrs)

    # Build arguments for view.py
    view_args = []
    if args.config:
        view_args.extend(["-c", args.config])
    elif args.imagery_addrs:
        view_args.append("-i")
        view_args.extend(args.imagery_addrs)

    if args.rgb:
        view_args.append("--rgb")

    cli = run_module("local_cli.py", cli_args)
    view = run_module("view.py", view_args)

    try:
        # Wait for both; if one exits, we still wait for the other unless interrupted.
        cli.wait()
        view.wait()
    except KeyboardInterrupt:
        cli.terminate()
        view.terminate()


if __name__ == "__main__":
    main()
