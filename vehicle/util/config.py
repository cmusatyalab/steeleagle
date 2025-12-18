import os

import toml


def import_config(path):
    """
    Import configuration file from environment variable.
    """
    with open(path) as file:
        cfg = toml.load(file)
        return cfg


CONFIG = None
if os.environ.get("CONFIGPATH"):
    CONFIG = import_config(os.environ.get("CONFIGPATH"))
elif os.path.isfile("config.toml"):
    CONFIG = import_config("config.toml")
else:
    raise ValueError(
        "No path provided for config file and no local file found. Try setting CONFIGPATH!"
    )

INTERNAL = None
if os.environ.get("INTERNALPATH"):
    INTERNAL = import_config(os.environ.get("INTERNALPATH"))
elif os.path.isfile(".internal.toml"):
    INTERNAL = import_config(".internal.toml")
else:
    raise ValueError(
        "No path provided for internal config file and no local file found. Try setting INTERNALPATH!"
    )


def query_config(access_token):
    """
    Allows for accessing the CONFIG using a plaintext access token.
    An access token indexes a specific socket name in the vehicle CONFIG.yaml.
    This must be formatted in a Pythonic module import format. For example, for
    the driver_to_hub telemetry socket under dataplane and hub, it would be
    requested using the id: hub.dataplane.driver_to_hub.telemetry.
    """
    indices = access_token.split(".")
    if indices[0] == "internal":
        result = INTERNAL
        indices = indices[1:]
    else:
        result = CONFIG
    for i in indices:
        if i not in result:
            raise ValueError(f"Malformed access token: {access_token}")
        result = result[i]  # Access the corresponding field
    return result
