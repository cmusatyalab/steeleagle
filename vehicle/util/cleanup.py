import signal


def register_cleanup_handler(func=None):
    # Register the signal handler for SIGTERM
    signal.signal(signal.SIGINT, func if func else signal_handler)
    signal.signal(signal.SIGTERM, func if func else signal_handler)


def signal_handler(signum, frame):
    """
    Custom signal handler that raises a SystemExit exception when SIGTERM is received.
    """
    raise SystemExit(1)  # Raise SystemExit to allow for cleanup
