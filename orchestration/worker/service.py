"""
worker/service.py

A simple long-running Python process that the orchestrator manages.
Prints a heartbeat every few seconds and handles SIGTERM gracefully.
"""

import logging
import signal
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [worker] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

_running = True


def _handle_signal(sig, frame):
    global _running
    log.info("Received signal %s, shutting down...", sig)
    _running = False


signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)


def main():
    log.info("Worker started (pid=%d)", os.getpid())
    counter = 0
    while _running:
        counter += 1
        log.info("Heartbeat #%d", counter)
        time.sleep(3)
    log.info("Worker exited cleanly")


if __name__ == "__main__":
    import os

    main()
