import logging
import os
import yaml

def import_config(path):
    '''
    Import configuration file from environment variable.
    '''
    with open(path, 'r') as file:
        cfg = yaml.safe_load(file)
        return cfg

CONFIG = None
if os.environ.get('CONFIGPATH'):
    CONFIG = import_config(os.environ.get('CONFIGPATH'))
elif os.path.isfile('config.yaml'):
    CONFIG = import_config('config.yaml')
else:
    raise ValueError(
            "No path provided for config file and no local file found. Try setting CONFIGPATH!"
            )

INTERNAL = None
if os.environ.get('INTERNALPATH'):
    INTERNAL = import_config(os.environ.get('INTERNALPATH'))
elif os.path.isfile('.internal.yaml'):
    INTERNAL = import_config('.internal.yaml')
else:
    raise ValueError(
            "No path provided for internal config file and no local file found. Try setting INTERNALPATH!"
            )

def query_config(access_token):
    '''
    Allows for accessing the CONFIG using a plaintext access token.
    An access token indexes a specific socket name in the vehicle CONFIG.yaml.
    This must be formatted in a Pythonic module import format. For example, for
    the driver_to_hub telemetry socket under dataplane and hub, it would be
    requested using the id: hub.dataplane.driver_to_hub.telemetry.
    '''
    indices = access_token.split('.')
    if indices[0] == 'internal':
        result = INTERNAL
        indices = indices[1:]
    else:
        result = CONFIG
    for i in indices:
        if i not in result.keys():
            raise ValueError(f"Malformed access token: {access_token}")
        result = result[i] # Access the corresponding field
    return result

def check_config():
    '''
    Ensures that there are no address conflicts between services.
    '''
    try:
        # Add all the service-based CONFIG to one traversible
        # entity for easy reading
        srv_cfg = query_config('services')
        srv_cfg.update(query_config('cloudlet'))
        srv_cfg.update(query_config('internal.services'))
        srv_cfg.update(query_config('internal.streams'))
        addrs = set([])
        seen = 0
        
        for key in srv_cfg:
            try:
                addrs.add(srv_cfg[key]['endpoint'])
                seen += 1
            except:
                pass
        if len(addrs) != seen:
            raise ValueError(f"Services have conflicting addresses! \
                    Check your config.yaml to ensure you are not using reserved addresses (8990-8999)")
    except Exception as e:
        raise
