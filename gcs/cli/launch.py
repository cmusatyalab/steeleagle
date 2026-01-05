import subprocess


def run_module(module):
    return subprocess.Popen(["uv", "run", module])


def main():
    cli = run_module("local_cli.py")
    view = run_module("view.py")

    try:
        cli.wait()
        view.wait()
    except KeyboardInterrupt:
        cli.terminate()
        view.terminate()


if __name__ == "__main__":
    main()
