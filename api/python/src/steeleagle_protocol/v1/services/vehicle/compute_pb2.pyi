from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class EngineLocation(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ENGINE_LOCATION_UNSPECIFIED: _ClassVar[EngineLocation]
    ENGINE_LOCATION_BOTH: _ClassVar[EngineLocation]
    ENGINE_LOCATION_REMOTE: _ClassVar[EngineLocation]
    ENGINE_LOCATION_LOCAL: _ClassVar[EngineLocation]

class Topic(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    TOPIC_UNSPECIFIED: _ClassVar[Topic]
    TOPIC_TELEMETRY: _ClassVar[Topic]
    TOPIC_FRAMES: _ClassVar[Topic]
ENGINE_LOCATION_UNSPECIFIED: EngineLocation
ENGINE_LOCATION_BOTH: EngineLocation
ENGINE_LOCATION_REMOTE: EngineLocation
ENGINE_LOCATION_LOCAL: EngineLocation
TOPIC_UNSPECIFIED: Topic
TOPIC_TELEMETRY: Topic
TOPIC_FRAMES: Topic

class EngineInfo(_message.Message):
    __slots__ = ("id", "location")
    ID_FIELD_NUMBER: _ClassVar[int]
    LOCATION_FIELD_NUMBER: _ClassVar[int]
    id: str
    location: EngineLocation
    def __init__(self, id: _Optional[str] = ..., location: _Optional[_Union[EngineLocation, str]] = ...) -> None: ...

class SetEnginesForTopicRequest(_message.Message):
    __slots__ = ("topic", "datasinks")
    TOPIC_FIELD_NUMBER: _ClassVar[int]
    DATASINKS_FIELD_NUMBER: _ClassVar[int]
    topic: Topic
    datasinks: _containers.RepeatedCompositeFieldContainer[EngineInfo]
    def __init__(self, topic: _Optional[_Union[Topic, str]] = ..., datasinks: _Optional[_Iterable[_Union[EngineInfo, _Mapping]]] = ...) -> None: ...

class SetEnginesForTopicResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...
