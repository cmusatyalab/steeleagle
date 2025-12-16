import griffe
from griffe import Alias, ExprName, ExprSubscript, ExprTuple, ExprAttribute
from typing import List
from collections import deque
from dataclasses import dataclass, asdict
from jinja2 import Environment, FileSystemLoader
import os
from pathlib import Path

""" API Type definitions for Jinja """
@dataclass
class Arg:
    name: str
    type: str
    comment: str = None

@dataclass
class Function:
    name: str
    label: str
    args: List[Arg]
    ret: str = None
    comment: str = None
    inheritance: str = None
    source: str = None

@dataclass
class Class:
    name: str
    functions: List[Function]
    attributes: List[Arg]
    comment: str = None
    inheritance: str = None
    source: str = None

@dataclass
class Module:
    name: str
    link: str
    comment: str = None

@dataclass
class Package:
    name: str
    functions: List[Function]
    attributes: List[Arg]
    classes: List[Class]
    submodules: List[Module]
    comment: str = None

OUTPUT_PATH = '../../../docs/docs/sdk/python/'
LINK_PREFIX = '/sdk/python/'
MODULES = [
    '../src/steeleagle_sdk/'
]

def resolve_annotation(annotation, module):
    if not annotation:
        return ''
    if isinstance(annotation, ExprName):
        if 'steeleagle_sdk' not in annotation.canonical_path:
            return annotation.canonical_path
        try:
            name = str(annotation)
            path = module.resolve(str(name)).split('.')
            typename = path[-1]
            path = path[:-1]
            link = '/'.join(path) + '#' + f'class-{typename.lower()}'
            return f'<Link to="{LINK_PREFIX}{link}">{name}</Link>'
        except Exception as e:
            return str(annotation) 
    elif isinstance(annotation, ExprAttribute):
        if 'steeleagle_sdk' not in annotation.canonical_path:
            return annotation.canonical_path
        path = annotation.canonical_path.split('.')
        typename = path[-1]
        path = path[:-1]
        link = '/'.join(path) + '#' + f'class-{typename.lower()}'
        return f'<Link to="{LINK_PREFIX}{link}">{annotation.canonical_name}</Link>'
    elif isinstance(annotation, ExprSubscript):
        return str(annotation.left) + f'[{resolve_annotation(annotation.slice, module)}]'
    elif isinstance(annotation, ExprTuple):
        return ', '.join([i for i in [resolve_annotation(item, module) for item in annotation] if i != ', ' and i != ''])
    elif isinstance(annotation, str):
        return annotation

def resolve_type(attribute, module):
    annotation = resolve_annotation(attribute.annotation, module)
    if annotation == '':
        return None
    else:
        return f'<code>{resolve_annotation(attribute.annotation, module)}</code>'

def resolve_base(expr, module):
    if not expr or expr == '':
        return None
    else:
        return f'<code>{resolve_annotation(expr, module)}</code>'
    
def get_attribute(attribute, module):
    name = attribute.name if hasattr(attribute, 'name') else None
    typehint = resolve_type(attribute, module)
    comment = attribute.description if hasattr(attribute, 'description') else None
    return Arg(name, typehint, comment)

def get_function(function, module, get_source=True):
    name = function.name
    label = 'async' if 'async' in function.labels else 'normal' 
    docstring = function.docstring.parse('google') if function.docstring else None
    comment = None
    args = []
    ret = None
    inheritance = None
    if function.docstring:
        docstring = function.docstring.parse('google')
        for section in docstring:
            if section.kind.value == 'text':
                comment = section.value
            elif section.kind.value == 'parameters':
                for param in section.value:
                    args.append(get_attribute(param, module))
            elif section.kind.value == 'returns':
                ret = get_attribute(section.value[0], module)
    source = None
    if get_source:
        with open(function.filepath, "r") as f:
            lines = f.readlines()
            source = "".join(lines[function.lineno - 1 : function.endlineno])
    return Function(name, label, args, ret, comment, inheritance, source)

def get_class(_class, module):
    name = _class.name
    comment = None
    functions = []
    attributes = []
    inheritance = None
    if len(_class.bases) > 0:
        bases = [resolve_base(b, module) for b in _class.bases]
        inheritance = ', '.join(bases)
    if _class.docstring:
        docstring = _class.docstring.parse('google')
        for section in docstring:
            if section.kind.value == 'text':
                comment = section.value.replace('->', '&#8594;') # Replace arrow characters
            elif section.kind.value == 'attributes':
                for attr in section.value:
                    attributes.append(get_attribute(attr, module))
    for _, function in _class.functions.items():
        functions.append(get_function(function, module, get_source=False))
    source = None
    with open(_class.filepath, "r") as f:
        lines = f.readlines()
        source = "".join(lines[_class.lineno - 1 : _class.endlineno])
    return Class(name, functions, attributes, comment, inheritance, source)

def get_module(module, parent):
    name = module.name
    path = str(parent.relative_package_filepath / module.name).replace('/__init__.py', '').replace('.py', '')
    link = f'{LINK_PREFIX}{path}'
    comment = None
    if module.docstring:
        docstring = module.docstring.parse('google')
        for section in docstring:
            if section.kind.value == 'text':
                comment = section.value.replace('->', '&#8594;').partition('\n')[0]
    return Module(name, link, comment)

def generate_pyfile_docs():
    template_path = Path(__file__).parent / 'templates/'
    environment = Environment(loader=FileSystemLoader(str(template_path)), trim_blocks=True, lstrip_blocks=True)
    doc_template = environment.get_template('pydoc.md')
    for pkg in MODULES:
        package = griffe.load(pkg) 
        seen = set([])
        modules = deque([package])
        while modules:
            # Get package name
            mod = modules.popleft()
            module_name = mod.name
            if mod.relative_package_filepath in seen:
                continue
            
            comment = None
            attributes = []
            if mod.docstring:
                docstring = mod.docstring.parse('google')
                for section in docstring:
                    if section.kind.value == 'text':
                        comment = section.value
                    elif section.kind.value == 'attributes':
                        for attr in section.value:
                            attr_obj = get_attribute(attr, mod)
                            # Capitalize and add period for inline attributes
                            attr_obj.comment = attr_obj.comment.capitalize() + '.'
                            attributes.append(attr_obj)
            
            functions = []
            classes = []
            submodules = []
            # Iterate through functions
            for name, member in mod.members.items():
                if member.is_alias:
                    continue
                elif member.is_function:
                    functions.append(get_function(member, mod))
                elif member.is_class:
                    classes.append(get_class(member, mod))
                elif member.is_module:
                    submodules.append(get_module(member, mod))
                    modules.append(member)
            seen.add(mod.relative_package_filepath)
            module_object = Package(module_name, functions, attributes, classes, submodules, comment)
            output_rel_path = str(mod.relative_package_filepath).replace('.py', '.md').replace('__init__', 'index')
            full_path = f'{OUTPUT_PATH}{output_rel_path}'
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            if module_name == 'steeleagle_sdk': # Do this only for the top level module
                full_path += '/index.md'
            with open(full_path, 'w') as f:
                f.write(doc_template.render(asdict(module_object)))

""" Protobuf Type definitions for Jinja """
@dataclass
class Type:
    name: str
    attributes: List[Arg]
    is_enum: bool
    comment: str = None

@dataclass
class RPC:
    name: str
    input: str
    output: str
    comment: str = None

@dataclass
class Service:
    name: str
    rpc: List[RPC]
    streaming: bool
    comment: str = None

@dataclass
class Protofile:
    name: str
    types: List[Type]
    services: List[Service]

PB_OUTPUT_PATH = '../../../docs/docs/sdk/native/'
PB_LINK_PREFIX = '/sdk/native'
PB_TYPE_NAMES = [
    'unknown',
    'double',
    'float',
    'int64',
    'uint64',
    'int32',
    'fixed64',
    'fixed32',
    'bool',
    'string',
    'group',
    'message',
    'bytes',
    'uint32',
    'enum',
    'sfixed32',
    'sfixed64',
    'sint32',
    'sint64'
]

from generate_api import get_comments
from google.protobuf import descriptor_pb2

def generate_native_source_docs():
    template_path = Path(__file__).parent / 'templates/'
    environment = Environment(loader=FileSystemLoader(str(template_path)), trim_blocks=True, lstrip_blocks=True)
    doc_template = environment.get_template('protodoc.md')
    
    file_fd = descriptor_pb2.FileDescriptorSet()
    with open(os.getenv('DESCPATH'), "rb") as f:
        file_fd.MergeFromString(f.read())

    for file in file_fd.file:
        filepath = file.name

        if 'google' in filepath:
            continue # Don't generate docs for Google files

        splits = file.name.split('/')
        filename = splits[-1].split('.')[0]
        
        # Map to find comments in the source code for eventual auto-documentation
        location_map = {tuple(loc.path): loc for loc in file.source_code_info.location}

        # Collect services
        services = []
        for i, service in enumerate(file.service):
            name = service.name
            comment = get_comments((6, i), location_map, docstring=True)
            rpcs = []
            for j, method in enumerate(service.method):
                # Create the input MD link
                input_link = method.input_type.replace('.steeleagle.protocol', '').replace('.', '/')
                input_name = method.input_type.split('.')[-1]
                input_md_link = input_name.replace(' ', '-').lower()
                input_href = input_link.replace(f'/{input_name}', f'#message-{input_md_link}')
                # Create the output MD link
                output_link = method.output_type.replace('.steeleagle.protocol', '').replace('.', '/')
                output_name = method.output_type.split('.')[-1]
                output_md_link = output_name.replace(' ', '-').lower()
                output_href = output_link.replace(f'/{output_name}', f'#message-{output_md_link}')
                # Final links
                input_doclink = f'<code><Link to="{PB_LINK_PREFIX}{input_href}">{input_name}</Link></code>'
                output_doclink = f'<code><Link to="{PB_LINK_PREFIX}{output_href}">{output_name}</Link></code>'
                rpcs.append(RPC(method.name, input_doclink, output_doclink, get_comments((6, i, 2, j), location_map, docstring=True)))
            services.append(Service(name, rpcs, method.server_streaming, comment))

        types = []
        # Collect enums
        for i, enum in enumerate(file.enum_type):
            name = enum.name
            comment = get_comments((5, i), location_map, docstring=True)
            values = []
            for j, value in enumerate(enum.value):
                values.append(Arg(value.name, f'`{j}`', get_comments((5, i, 2, j), location_map)))
            types.append(Type(name, values, True, comment))

        # Collect messages
        for i, message in enumerate(file.message_type):
            name = message.name
            comment = get_comments((4, i), location_map, docstring=True)
            fields = []
            for j, field in enumerate(message.field):
                ftype = PB_TYPE_NAMES[field.type]
                if ftype == 'enum' or ftype == 'message':
                    link = field.type_name.replace('.steeleagle.protocol', '').replace('.', '/')
                    if 'google' in link:
                        ftype = f'<code>{link}</code>'
                    else:
                        type_name = field.type_name.split('.')[-1]
                        md_link = type_name.replace(' ', '-').lower()
                        href = link.replace(f'/{type_name}', f'#{ftype}-{md_link}')
                        ftype = f'<code><Link to="{PB_LINK_PREFIX}{href}">{type_name}</Link></code>'
                else:
                    ftype = f'`{ftype}`'
                fields.append(Arg(field.name, ftype, get_comments((4, i, 2, j), location_map)))
            types.append(Type(name, fields, False, comment))
        
        protofile = Protofile(filename, types, services)

        full_path = f'{PB_OUTPUT_PATH}{filepath}'.replace('.proto', '.md')
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w') as f:
            f.write(doc_template.render(asdict(protofile)))

generate_pyfile_docs()
generate_native_source_docs()
