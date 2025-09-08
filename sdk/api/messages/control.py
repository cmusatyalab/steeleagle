''' Enums '''
from enum import Enum
from dataclasses import dataclass
from api.base import Datatype

class AltitudeMode(Enum):

    ABSOLUTE = 0
    '''Meters above Mean Sea Level'''
    RELATIVE = 1
    '''Meters above takeoff location'''

class HeadingMode(Enum):

    TO_TARGET = 0
    '''Orient towards the target location'''
    HEADING_START = 1
    '''Orient towards the given heading'''

class ReferenceFrame(Enum):

    BODY = 0
    '''Vehicle reference frame'''
    ENU = 1
    '''Global (East, North, Up) reference frame'''

class PoseMode(Enum):

    ANGLE = 0
    '''Absolute angle'''
    OFFSET = 1
    '''Offset from current'''
    VELOCITY = 2
    '''Rotational velocities'''


@dataclass
class ImagingSensorConfiguration(Datatype):

    id: int
    '''Target imaging sensor ID'''
    set_primary: bool
    '''Set this sensor as the primary stream'''
    set_fps: int
    '''Target FPS for stream'''


