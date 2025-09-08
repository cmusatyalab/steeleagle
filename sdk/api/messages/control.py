''' Enums '''
from enum import Enum
from dataclasses import dataclass
from api.base import Datatype
from dsl.compiler.registry import register_data 

class AltitudeModeValue(Enum):

    ABSOLUTE = 0
    '''Meters above Mean Sea Level'''
    RELATIVE = 1
    '''Meters above takeoff location'''

class HeadingModeValue(Enum):

    TO_TARGET = 0
    '''Orient towards the target location'''
    HEADING_START = 1
    '''Orient towards the given heading'''

class ReferenceFrameValue(Enum):

    BODY = 0
    '''Vehicle reference frame'''
    ENU = 1
    '''Global (East, North, Up) reference frame'''
    
class PoseModeValue(Enum):

    ANGLE = 0
    '''Absolute angle'''
    OFFSET = 1
    '''Offset from current'''
    VELOCITY = 2
    '''Rotational velocities'''

@register_data
@dataclass
class HeadingMode(Datatype):
    mode: HeadingModeValue
  
@register_data
@dataclass
class AltitudeMode(Datatype):
    mode: AltitudeModeValue


@register_data
@dataclass
class ReferenceFrame(Datatype):
    mode: ReferenceFrameValue

@register_data
@dataclass
class PoseMode(Datatype):
    mode: PoseModeValue

@register_data
@dataclass
class ImagingSensorConfiguration(Datatype):

    id: int
    '''Target imaging sensor ID'''
    set_primary: bool
    '''Set this sensor as the primary stream'''
    set_fps: int
    '''Target FPS for stream'''


