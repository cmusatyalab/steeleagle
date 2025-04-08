import logging

logging_format = "%(asctime)s [%(levelname)s] (%(filename)s:%(lineno)d) - %(message)s"

def setup_logging(logger, logging_config):
    if logging_config is not None:
        logging.basicConfig(level=logging_config.get('log_level', logging.INFO), format=logging_format)
    else:
        logging.basicConfig(level=logging.INFO, format=logging_format)

    log_file = logging_config.get('log_file')
    if log_file is not None:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(logging_format))
        logger.addHandler(file_handler)
