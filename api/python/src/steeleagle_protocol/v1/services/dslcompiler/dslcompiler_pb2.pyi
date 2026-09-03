from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class GetSchemaRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetSchemaResponse(_message.Message):
    __slots__ = ("actions", "events", "datatypes", "enums", "imports", "default_role")
    class ActionsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: TypeSchema
        def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[TypeSchema, _Mapping]] = ...) -> None: ...
    class EventsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: TypeSchema
        def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[TypeSchema, _Mapping]] = ...) -> None: ...
    class DatatypesEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: TypeSchema
        def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[TypeSchema, _Mapping]] = ...) -> None: ...
    class EnumsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: EnumSchema
        def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[EnumSchema, _Mapping]] = ...) -> None: ...
    ACTIONS_FIELD_NUMBER: _ClassVar[int]
    EVENTS_FIELD_NUMBER: _ClassVar[int]
    DATATYPES_FIELD_NUMBER: _ClassVar[int]
    ENUMS_FIELD_NUMBER: _ClassVar[int]
    IMPORTS_FIELD_NUMBER: _ClassVar[int]
    DEFAULT_ROLE_FIELD_NUMBER: _ClassVar[int]
    actions: _containers.MessageMap[str, TypeSchema]
    events: _containers.MessageMap[str, TypeSchema]
    datatypes: _containers.MessageMap[str, TypeSchema]
    enums: _containers.MessageMap[str, EnumSchema]
    imports: _containers.RepeatedCompositeFieldContainer[ImportSpec]
    default_role: str
    def __init__(self, actions: _Optional[_Mapping[str, TypeSchema]] = ..., events: _Optional[_Mapping[str, TypeSchema]] = ..., datatypes: _Optional[_Mapping[str, TypeSchema]] = ..., enums: _Optional[_Mapping[str, EnumSchema]] = ..., imports: _Optional[_Iterable[_Union[ImportSpec, _Mapping]]] = ..., default_role: _Optional[str] = ...) -> None: ...

class ImportSpec(_message.Message):
    __slots__ = ("alias", "path", "version")
    ALIAS_FIELD_NUMBER: _ClassVar[int]
    PATH_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    alias: str
    path: str
    version: str
    def __init__(self, alias: _Optional[str] = ..., path: _Optional[str] = ..., version: _Optional[str] = ...) -> None: ...

class TypeSchema(_message.Message):
    __slots__ = ("description", "fields")
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    FIELDS_FIELD_NUMBER: _ClassVar[int]
    description: str
    fields: _containers.RepeatedCompositeFieldContainer[FieldSchema]
    def __init__(self, description: _Optional[str] = ..., fields: _Optional[_Iterable[_Union[FieldSchema, _Mapping]]] = ...) -> None: ...

class EnumSchema(_message.Message):
    __slots__ = ("description", "values")
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    VALUES_FIELD_NUMBER: _ClassVar[int]
    description: str
    values: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, description: _Optional[str] = ..., values: _Optional[_Iterable[str]] = ...) -> None: ...

class FieldSchema(_message.Message):
    __slots__ = ("name", "type", "required", "description", "default_value", "object_type", "nested_fields", "enum_type", "map_feature")
    NAME_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    REQUIRED_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    DEFAULT_VALUE_FIELD_NUMBER: _ClassVar[int]
    OBJECT_TYPE_FIELD_NUMBER: _ClassVar[int]
    NESTED_FIELDS_FIELD_NUMBER: _ClassVar[int]
    ENUM_TYPE_FIELD_NUMBER: _ClassVar[int]
    MAP_FEATURE_FIELD_NUMBER: _ClassVar[int]
    name: str
    type: str
    required: bool
    description: str
    default_value: str
    object_type: str
    nested_fields: _containers.RepeatedCompositeFieldContainer[FieldSchema]
    enum_type: str
    map_feature: bool
    def __init__(self, name: _Optional[str] = ..., type: _Optional[str] = ..., required: _Optional[bool] = ..., description: _Optional[str] = ..., default_value: _Optional[str] = ..., object_type: _Optional[str] = ..., nested_fields: _Optional[_Iterable[_Union[FieldSchema, _Mapping]]] = ..., enum_type: _Optional[str] = ..., map_feature: _Optional[bool] = ...) -> None: ...

class Node(_message.Message):
    __slots__ = ("instance_id", "type_name", "params")
    class ParamsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: FieldValue
        def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[FieldValue, _Mapping]] = ...) -> None: ...
    INSTANCE_ID_FIELD_NUMBER: _ClassVar[int]
    TYPE_NAME_FIELD_NUMBER: _ClassVar[int]
    PARAMS_FIELD_NUMBER: _ClassVar[int]
    instance_id: str
    type_name: str
    params: _containers.MessageMap[str, FieldValue]
    def __init__(self, instance_id: _Optional[str] = ..., type_name: _Optional[str] = ..., params: _Optional[_Mapping[str, FieldValue]] = ...) -> None: ...

class EventInstance(_message.Message):
    __slots__ = ("instance_id", "type_name", "params")
    class ParamsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: FieldValue
        def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[FieldValue, _Mapping]] = ...) -> None: ...
    INSTANCE_ID_FIELD_NUMBER: _ClassVar[int]
    TYPE_NAME_FIELD_NUMBER: _ClassVar[int]
    PARAMS_FIELD_NUMBER: _ClassVar[int]
    instance_id: str
    type_name: str
    params: _containers.MessageMap[str, FieldValue]
    def __init__(self, instance_id: _Optional[str] = ..., type_name: _Optional[str] = ..., params: _Optional[_Mapping[str, FieldValue]] = ...) -> None: ...

class Edge(_message.Message):
    __slots__ = ("source", "event_id", "target")
    SOURCE_FIELD_NUMBER: _ClassVar[int]
    EVENT_ID_FIELD_NUMBER: _ClassVar[int]
    TARGET_FIELD_NUMBER: _ClassVar[int]
    source: str
    event_id: str
    target: str
    def __init__(self, source: _Optional[str] = ..., event_id: _Optional[str] = ..., target: _Optional[str] = ...) -> None: ...

class FieldValue(_message.Message):
    __slots__ = ("float_value", "int_value", "string_value", "bool_value", "ident_ref", "array_value", "inline_value")
    FLOAT_VALUE_FIELD_NUMBER: _ClassVar[int]
    INT_VALUE_FIELD_NUMBER: _ClassVar[int]
    STRING_VALUE_FIELD_NUMBER: _ClassVar[int]
    BOOL_VALUE_FIELD_NUMBER: _ClassVar[int]
    IDENT_REF_FIELD_NUMBER: _ClassVar[int]
    ARRAY_VALUE_FIELD_NUMBER: _ClassVar[int]
    INLINE_VALUE_FIELD_NUMBER: _ClassVar[int]
    float_value: float
    int_value: int
    string_value: str
    bool_value: bool
    ident_ref: str
    array_value: FieldValueArray
    inline_value: InlineCtorValue
    def __init__(self, float_value: _Optional[float] = ..., int_value: _Optional[int] = ..., string_value: _Optional[str] = ..., bool_value: _Optional[bool] = ..., ident_ref: _Optional[str] = ..., array_value: _Optional[_Union[FieldValueArray, _Mapping]] = ..., inline_value: _Optional[_Union[InlineCtorValue, _Mapping]] = ...) -> None: ...

class FieldValueArray(_message.Message):
    __slots__ = ("elems",)
    ELEMS_FIELD_NUMBER: _ClassVar[int]
    elems: _containers.RepeatedCompositeFieldContainer[FieldValue]
    def __init__(self, elems: _Optional[_Iterable[_Union[FieldValue, _Mapping]]] = ...) -> None: ...

class InlineCtorValue(_message.Message):
    __slots__ = ("type_name", "args")
    class ArgsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: FieldValue
        def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[FieldValue, _Mapping]] = ...) -> None: ...
    TYPE_NAME_FIELD_NUMBER: _ClassVar[int]
    ARGS_FIELD_NUMBER: _ClassVar[int]
    type_name: str
    args: _containers.MessageMap[str, FieldValue]
    def __init__(self, type_name: _Optional[str] = ..., args: _Optional[_Mapping[str, FieldValue]] = ...) -> None: ...

class MissionGraph(_message.Message):
    __slots__ = ("nodes", "events", "edges", "start_id", "role", "imports")
    NODES_FIELD_NUMBER: _ClassVar[int]
    EVENTS_FIELD_NUMBER: _ClassVar[int]
    EDGES_FIELD_NUMBER: _ClassVar[int]
    START_ID_FIELD_NUMBER: _ClassVar[int]
    ROLE_FIELD_NUMBER: _ClassVar[int]
    IMPORTS_FIELD_NUMBER: _ClassVar[int]
    nodes: _containers.RepeatedCompositeFieldContainer[Node]
    events: _containers.RepeatedCompositeFieldContainer[EventInstance]
    edges: _containers.RepeatedCompositeFieldContainer[Edge]
    start_id: str
    role: str
    imports: _containers.RepeatedCompositeFieldContainer[ImportSpec]
    def __init__(self, nodes: _Optional[_Iterable[_Union[Node, _Mapping]]] = ..., events: _Optional[_Iterable[_Union[EventInstance, _Mapping]]] = ..., edges: _Optional[_Iterable[_Union[Edge, _Mapping]]] = ..., start_id: _Optional[str] = ..., role: _Optional[str] = ..., imports: _Optional[_Iterable[_Union[ImportSpec, _Mapping]]] = ...) -> None: ...

class CompileError(_message.Message):
    __slots__ = ("node_id", "event_id", "message")
    NODE_ID_FIELD_NUMBER: _ClassVar[int]
    EVENT_ID_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    node_id: str
    event_id: str
    message: str
    def __init__(self, node_id: _Optional[str] = ..., event_id: _Optional[str] = ..., message: _Optional[str] = ...) -> None: ...

class ValidateRequest(_message.Message):
    __slots__ = ("mission",)
    MISSION_FIELD_NUMBER: _ClassVar[int]
    mission: MissionGraph
    def __init__(self, mission: _Optional[_Union[MissionGraph, _Mapping]] = ...) -> None: ...

class ValidateResponse(_message.Message):
    __slots__ = ("ok", "errors")
    OK_FIELD_NUMBER: _ClassVar[int]
    ERRORS_FIELD_NUMBER: _ClassVar[int]
    ok: bool
    errors: _containers.RepeatedCompositeFieldContainer[CompileError]
    def __init__(self, ok: _Optional[bool] = ..., errors: _Optional[_Iterable[_Union[CompileError, _Mapping]]] = ...) -> None: ...

class BuildRequest(_message.Message):
    __slots__ = ("mission", "geojson")
    MISSION_FIELD_NUMBER: _ClassVar[int]
    GEOJSON_FIELD_NUMBER: _ClassVar[int]
    mission: MissionGraph
    geojson: bytes
    def __init__(self, mission: _Optional[_Union[MissionGraph, _Mapping]] = ..., geojson: _Optional[bytes] = ...) -> None: ...

class BuildChunk(_message.Message):
    __slots__ = ("arch", "data", "done", "errors")
    ARCH_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    DONE_FIELD_NUMBER: _ClassVar[int]
    ERRORS_FIELD_NUMBER: _ClassVar[int]
    arch: str
    data: bytes
    done: bool
    errors: _containers.RepeatedCompositeFieldContainer[CompileError]
    def __init__(self, arch: _Optional[str] = ..., data: _Optional[bytes] = ..., done: _Optional[bool] = ..., errors: _Optional[_Iterable[_Union[CompileError, _Mapping]]] = ...) -> None: ...

class ParseDslRequest(_message.Message):
    __slots__ = ("dsl",)
    DSL_FIELD_NUMBER: _ClassVar[int]
    dsl: str
    def __init__(self, dsl: _Optional[str] = ...) -> None: ...

class ParseDslResponse(_message.Message):
    __slots__ = ("ok", "mission", "errors")
    OK_FIELD_NUMBER: _ClassVar[int]
    MISSION_FIELD_NUMBER: _ClassVar[int]
    ERRORS_FIELD_NUMBER: _ClassVar[int]
    ok: bool
    mission: MissionGraph
    errors: _containers.RepeatedCompositeFieldContainer[CompileError]
    def __init__(self, ok: _Optional[bool] = ..., mission: _Optional[_Union[MissionGraph, _Mapping]] = ..., errors: _Optional[_Iterable[_Union[CompileError, _Mapping]]] = ...) -> None: ...
