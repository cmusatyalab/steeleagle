import argparse

import uvicorn

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to [default=127.0.0.1, use 0.0.0.0 to bind to all interfaces]",
    )

    parser.add_argument(
        "--port",
        default=8002,
        type=int,
        help="Port to bind to [default=8002]",
    )

    args, _ = parser.parse_known_args()

    uvicorn.run(
        "app.api:app",
        host=args.host,
        port=args.port,
        reload=True,
        log_level="critical",
        # Open log streams (/api/daemons/logs/stream) never finish on their
        # own, so a graceful shutdown would wait on them forever; cancel
        # whatever is still running after this many seconds.
        timeout_graceful_shutdown=2,
    )
