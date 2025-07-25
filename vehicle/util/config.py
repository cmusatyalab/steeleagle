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

config = None
if os.environ.get('CONFIGPATH'):
    config = import_config(os.environ.get('CONFIGPATH'))
else:
    raise ValueError("No path provided for config file. Make sure to set CONFIGPATH!")

internal = None
if os.environ.get('INTERNALPATH'):
    internal = import_config(os.environ.get('INTERNALPATH'))
else:
    raise ValueError("No path provided for internal config file. Make sure to set INTERNALPATH!")

def query_config(access_token):
    '''
    Allows for accessing the config using a plaintext access token.
    An access token indexes a specific socket name in the vehicle config.yaml.
    This must be formatted in a Pythonic module import format. For example, for
    the driver_to_hub telemetry socket under dataplane and hub, it would be
    requested using the id: hub.dataplane.driver_to_hub.telemetry.
    '''
    indices = access_token.split('.')
    if indices[0] == 'internal':
        result = internal
    else:
        result = config
    for i in indices:
        if i not in result.keys():
            raise ValueError(f"Malformed access token: {access_token}")
        result = result[i] # Access the corresponding field
    return result

def check_config() -> bool:
    '''
    Ensures that there are no address conflicts between services.
    '''
    try:
        ctrl = query_config('internal.control_service.endpoint')
        telem = query_config('internal.telemetry.endpoint')
        img = query_config('internal.imaging.endpoint')
        msn = query_config('internal.mission_service.endpoint')
        cmp = query_config('internal.compute_service.endpoint')
        lcmp = query_config('internal.local_compute.endpoint')
        res = query_config('internal.results.endpoint')
        ctrl_srv = query_config('services.control_service.endpoint')
        rep_srv = query_config('services.report_service.endpoint')
        cmp_srv = query_config('services.compute_service.endpoint')
        if len(set([ctrl_srv, rep_srv, cmp_srv, ctrl, telem, img, msn, cmp, lcmp, res])) != 10:
            raise ValueError(f"Services have conflicting addresses! \
                    Check your config.yaml to ensure you are not using reserved addresses {ctrl, telem, img}")
        return True
    except Exception as e:
        print(f"Configuration check failed, reason: {e}")
        return False
