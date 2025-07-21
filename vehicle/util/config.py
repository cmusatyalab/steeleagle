import logging
import os
import yaml

def import_config():
    '''
    Import configuration file from environment variable.
    '''
    config_path = os.environ.get('CONFIGPATH')
    with open(config_path, 'r') as file:
        cfg = yaml.safe_load(file)
        return cfg

config = import_config()

def query_config(access_token):
    '''
    Allows for accessing the config using a plaintext access token.
    An access token indexes a specific socket name in the vehicle config.yaml.
    This must be formatted in a Pythonic module import format. For example, for
    the driver_to_hub telemetry socket under dataplane and hub, it would be
    requested using the id: hub.dataplane.driver_to_hub.telemetry.
    '''
    indices = access_token.split('.')
    result = config
    for i in indices:
        if i not in result.keys():
            raise ValueError(f"Malformed access token: {access_token}")
        result = result[i] # Access the corresponding field
    return result

def setup_logging(logger, access_token=None):
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
