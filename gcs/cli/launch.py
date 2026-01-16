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
    p = argparse.ArgumentParser(description="Launch local CLI + viewer")
    p.add_argument(
        "-a",
        "--addr",
        default="unix:///tmp/kernel.sock",
        help="gRPC kernel address for local_cli.py",
    )
    p.add_argument(
        "-i",
        "--imagery-addr",
        default="ipc:///tmp/imagery.sock",
        help="ZMQ imagery address for view.py",
    )
    p.add_argument(
        "--rgb",
        action="store_true",
        help="Tell view.py to treat frames as RGB and convert to BGR",
    )
    args = p.parse_args()

    cli_args = ["-a", args.addr]
    view_args = ["-i", args.imagery_addr]
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
    parser = argparse.ArgumentParser(
        description="Stripped down CLI for SteelEagle vehicle control."
    )
    parser.add_argument(
        "--kernel",
        "-k",
        type=str,
        default="unix:///tmp/kernel.sock",
        help="Address of kernel services"
    )
    parser.add_argument(
        "--imagery",
        "-i",
        type=str,
        default="unix:///tmp/imagery.sock",
        help="Address of imagery"
    )
    args = parser.parse_args()

    main(args)
