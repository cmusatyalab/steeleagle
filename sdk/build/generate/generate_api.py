import sys
from google.protobuf import descriptor_pb2
import os
from typing import List
from dataclasses import dataclass
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

_SKIP_FILES = [
    'services/remote_service.proto',
    'services/mission_service.proto',
    'services/flight_log_service.proto',
    'messages/compute_payload.proto',
    'testing/testing.proto',
    'google/protobuf/timestamp.proto',
    'google/protobuf/duration.proto',
    'google/protobuf/any.proto'
]

''' Type definitions for Jinja '''
@dataclass
class EnumValue:
    name: str
    comment: str = None

@dataclass
class Enum:
    name: str
    values: List[EnumValue]
    comment: str = None

@dataclass
class Field:
    name: str
    type: str
    comment: str = None
    enum: Enum = None

@dataclass
class Type:
    name: str
    fields: List[Field]
    comment: str = None

@dataclass
class Action:
    name: str
    fields: List[Field]
    streaming: bool
    comment: str = None

_MESSAGE_DIR = '../../api/datatypes'
_ACTION_DIR = '../../api/actions/primitives'

''' Functions '''
def generate():
    '''
    Generates params, messages, and actions from a protocol descriptor file.
    '''
    protocol_fds = descriptor_pb2.FileDescriptorSet()
    with open(os.getenv('DESCPATH'), "rb") as f:
        protocol_fds.MergeFromString(f.read())
    for file in protocol_fds.file:
        if file.name in _SKIP_FILES:
            continue # Don't generate types for this file!
        
        splits = file.name.split('/')
        filename = splits[-1].split('.')[0]
        
        # Jinja context
        action_context = {
            'filename': filename,
            'param_file': None,
            'comment': None,
            'service_name': None,
            'stubs': [],
            'imports': []
        }
        type_context = {
            'filename': filename,
            'types': [],
            'imports': []
        }

        # Map to find comments in the source code for eventual auto-documentation
        location_map = {tuple(loc.path): loc for loc in file.source_code_info.location}
        
        # Add dependencies
        for dependency in file.dependency:
            dependency = dependency.split('.')[-2] # Remove .proto suffix
            if '/' in dependency:
                dependency = dependency.split('/')[-1]
            action_context['imports'].append(f'from ...datatypes import {dependency} as {dependency}')
            type_context['imports'].append(f'from ..datatypes import {dependency} as {dependency}')
        
        # Collect all the enums
        enum_map = {}
        for i, enum in enumerate(file.enum_type):
            values = []
            for j, value in enumerate(enum.value):
                values.append(
                        EnumValue(name=value.name, comment=get_comments((5, i, 2, j), location_map))
                        )
            enum_map[enum.name] = Enum(name=enum.name, comment=get_comments((5, i), location_map), values=values)
        
        # Write messages
        field_map = {}
        for i, message in enumerate(file.message_type):
            if 'Request' in message.name or (message.name != 'Response' and 'Response' in message.name):
                field_map[message.name] = (get_fields(message.field, enum_map), i) # Cache parameters for later
                continue # Skip this if it's an RPC request; they are not in the Python API
            fields = get_fields(message.field, enum_map)
            message_fields = []
            for field_name, typ, path_type, enum, index in fields:
                field = Field(
                        name=field_name, type=typ.replace(f'{filename}.', ''), 
                        comment=get_comments((4, i, path_type, index), location_map),
                        enum=enum
                        )
                message_fields.append(field)
            message = Type(name=message.name, comment=get_comments((4, i), location_map), fields=message_fields)
            type_context['types'].append(message)
        
        # Write services
        for i, service in enumerate(file.service):
            action_context['service_name'] = service.name
            action_context['comment'] = get_comments((6, i), location_map)
            for j, method in enumerate(service.method):
                # Retrieve the path data from the first time we traversed the messages
                fields, message_index = field_map[f"{method.name}Request"]
                action_fields = []
                for k, (field_name, typ, path_type, enum, index) in enumerate(fields):
                    field = Field(
                            name=field_name, type=typ.replace(f'{filename}.', ''), 
                            comment=get_comments((4, message_index, path_type, index), location_map),
                            enum=enum
                            )
                    action_fields.append(field)
                action = Action(name=method.name, comment=get_comments((6, i, 2, j), location_map), fields=action_fields, streaming=False)
                if method.client_streaming and method.server_streaming:
                    raise NotImplemented("No generation method for method type: bidirectional stream!")
                elif method.client_streaming:
                    raise NotImplemented("No generation method for method type: client stream!")
                elif method.server_streaming:
                    action.streaming = True
                action_context['stubs'].append(action)

        template_path = Path(__file__).parent / 'templates/'
        environment = Environment(loader=FileSystemLoader(str(template_path)), trim_blocks=True, lstrip_blocks=True)
        if action_context['service_name']:
            # Write both action and param file
            output_file = action_context['service_name'].lower()
            action_context['param_file'] = output_file
            template = environment.get_template('action.py')
            output_path = Path(__file__).parent / f'{_ACTION_DIR}/{output_file}.py'
            with open(output_path, 'w') as f:
                f.write(template.render(action_context))
            if len(type_context['types']):
                template = environment.get_template('datatype.py')
                output_path = Path(__file__).parent / f'{_MESSAGE_DIR}/{output_file}.py'
                with open(output_path, 'w') as f:
                    f.write(template.render(type_context))
        else:
            # Write normal type file
            template = environment.get_template('datatype.py')
            output_path = Path(__file__).parent / f'{_MESSAGE_DIR}/{filename}.py'
            with open(output_path, 'w') as f:
                f.write(template.render(type_context))

def get_fields(fields, enum_map):
    '''
    Get the fields associated with a message.
    '''
    result = []
    # Convert the protobuf enum type to a Pythonic type
    for i, field in enumerate(fields):
        # This represents where the field is located in the Protobuf file path
        # NOTE: In future, can be modified to support nested enums and messages
        enum = None
        path_type = 2
        if field.type in [1, 2]: 
            typ = 'float'
        elif field.type in [3, 4, 5, 6, 7, 13, 15, 16, 17, 18]:
            typ = 'int'
        elif field.type == 8:
            typ = 'bool'
        elif field.type == 9:
            typ = 'str'
        elif field.type == 12:
            typ = 'bytes'
        elif field.type in [11, 14]:
            splits = field.type_name.split('.')
            file = splits[-2]
            typ = splits[-1]
            if typ == 'Request':
                continue # Skip request typed fields because they aren't in the Python API
            elif typ in enum_map:
                enum = enum_map[typ]
            elif 'service' in file:
                typ = f'params.{typ}'
            else:
                typ = f'{file}.{typ}'
        else:
            raise ValueError(f'Unknown field type {field.type}!')
        if field.proto3_optional == 1: # This is an optional field!
            typ = f'Optional[{typ}]'
        elif field.label == 3:
            typ = f'List[{typ}]'

        result.append((field.name, typ, path_type, enum, i))
    return result

def get_comments(path, location_map):
    '''
    Retrieves comments for a given path within a protocol descriptor file.
    '''
    comments = []
    leading_comments = location_map.get(path).leading_comments.strip()
    if leading_comments:
        comments.append(leading_comments.replace('\n', ''))
    trailing_comments = location_map.get(path).trailing_comments.strip()
    if trailing_comments:
        comments.append(trailing_comments.replace('\n', ''))
    if len(comments):
        return f"'''{'. '.join(comments)}'''"
    else:
        return ""

generate()
