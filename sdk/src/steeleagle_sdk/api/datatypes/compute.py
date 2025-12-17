from enum import Enum
from ._base import Datatype


class DatasinkLocation(int, Enum):
    """Denotes where a datasink is located.

    Attributes:
        REMOTE (0): remote location (network hop required)
        LOCAL (1): local location (IPC)
    """

    REMOTE = 0
    LOCAL = 1


class DatasinkInfo(Datatype):
    """Information about a datasink.

    Attributes:
        id (str): datasink ID
        location (DatasinkLocation): datasink location
    """

    id: str
    location: DatasinkLocation
