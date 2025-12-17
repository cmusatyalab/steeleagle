import signal


def register_cleanup_handler(func=None):
    # Register the signal handler for SIGTERM
    signal.signal(signal.SIGINT, signal_handler if not func else func)
    signal.signal(signal.SIGTERM, signal_handler if not func else func)


def signal_handler(signum, frame):
    """
    Custom signal handler that raises a SystemExit exception when SIGTERM is received.
    """
    raise SystemExit(1)  # Raise SystemExit to allow for cleanup
