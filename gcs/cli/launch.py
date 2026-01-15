import subprocess
import argparse


def run_module(module, addr):
    return subprocess.Popen(["uv", "run", module, '-a', addr])


def main(args):
    cli = run_module("local_cli.py", args.kernel)
    view = run_module("view.py", args.imagery)

    try:
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
