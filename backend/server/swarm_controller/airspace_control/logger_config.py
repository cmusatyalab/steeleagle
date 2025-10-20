import logging
import sys
from pathlib import Path
from datetime import datetime


def setup_airspace_logging(log_level=logging.INFO, log_dir="logs", filemode='w'):
    """
    Configure simple logging for the airspace control system.
    Creates basic loggers with file and console output.
    """

    # Create logs directory if it doesn't exist
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)

    # Create formatters
    detailed_formatter = logging.Formatter(
        "%(asctime)s | %(name)s | %(levelname)s | %(funcName)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s", datefmt="%H:%M:%S"
    )

    # Set up root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear any existing handlers
    root_logger.handlers.clear()

    # Console handler for immediate feedback
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)

    # Main application log file (all events)
    app_handler = logging.FileHandler(log_path / "airspace_control.log", mode=filemode)
    app_handler.setLevel(log_level)
    app_handler.setFormatter(detailed_formatter)

    # Security/audit log for critical operations
    security_handler = logging.FileHandler(log_path / "airspace_security.log", mode=filemode)
    security_handler.setLevel(logging.WARNING)
    security_handler.setFormatter(detailed_formatter)

    # Add handlers to root logger
    root_logger.addHandler(console_handler)
    root_logger.addHandler(app_handler)

    # Set up security logger
    security_logger = logging.getLogger("airspace.security")
    security_logger.addHandler(security_handler)
    security_logger.propagate = False  # Don't send to root logger

    # Set up specific loggers
    engine_logger = logging.getLogger("airspace.engine")
    engine_logger.setLevel(log_level)

    region_logger = logging.getLogger("airspace.region")
    region_logger.setLevel(log_level)

    return {
        "engine": engine_logger,
        "region": region_logger,
        "security": security_logger,
    }


class AirspaceLoggerAdapter(logging.LoggerAdapter):
    """
    Logger adapter that adds contextual information like drone_id and region_id
    """

    def process(self, msg, kwargs):
        drone_id = self.extra.get("drone_id")
        region_id = self.extra.get("region_id")

        context_parts = []
        if drone_id is not None:
            context_parts.append(f"drone:{drone_id}")
        if region_id is not None:
            context_parts.append(f"region:{region_id}")

        if context_parts:
            separator = ' /\\ '
            context = f"[{separator.join(context_parts)}] "
            return f"{context}{msg}", kwargs
        return msg, kwargs
