import logging
import os
from utils.config import query_config

def setup_logging(access_token):
    '''
    Setup logger based on config file for a specific service.
    The provided access token indexes the service within the
    config file.
    '''
    logging_format = "%(asctime)s [%(levelname)s] (%(filename)s:%(lineno)d) - %(message)s"
    logging_config = None
    if access_token is not None:
        logging_config = query_config(access_token)
    if logging_config is not None:
        logging.basicConfig(level=logging_config['log_level'], format=logging_format, force=True)
    else:
        # If no logging config exists, default to INFO
        logging.basicConfig(level='INFO', format=logging_format)
        return

    # Log output to file, if requested
    log_file = logging_config['log_file']
    if log_file:
        file_handler = logging.FileHandler(log_file, mode='w')
        file_handler.setFormatter(logging.Formatter(logging_format))
        file_handler.setLevel(logging_config['log_level'])
        logging.getLogger().addHandler(file_handler)
