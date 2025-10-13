import griffe
from typing import List
from collections import deque
from dataclasses import dataclass, asdict
from jinja2 import Environment, FileSystemLoader
import os
from pathlib import Path

""" Type definitions for Jinja """
@dataclass
class Arg:
    name: str
    type: str
    comment: str = None

@dataclass
class Function:
    name: str
    signature: str
    args: List[Arg]
    ret: str = None
    comment: str = None
    inheritance: str = None

@dataclass
class Class:
    name: str
    functions: List[Function]
    attributes: List[Arg]
    comment: str = None
    inheritance: str = None

@dataclass
class Package:
    name: str
    functions: List[Function]
    attributes: List[Arg]
    classes: List[Class]
    comment: str = None

OUTPUT_PATH = '../../../docs/docs/sdk/package/'
MODULES = [
    '../../api',
    '../../dsl'
]

def resolve_type(annotation, package):
    if not annotation:
        return None
    return f'`{str(annotation)}`'
    
def get_attribute(attribute, package):
    name = attribute.name if hasattr(attribute, 'name') else None
    typehint = resolve_type(attribute.annotation, attribute)
    comment = attribute.description if hasattr(attribute, 'description') else None
    return Arg(name, typehint, comment)

def get_function(function, package):
    name = function.name
    signature = f'{"async def " if "async" in function.labels else "def "}{function.signature()}' 
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
                    args.append(get_attribute(param, package))
            elif section.kind.value == 'returns':
                ret = get_attribute(section.value[0], package)
    return Function(name, signature, args, ret, comment, inheritance)

def get_class(_class, package):
    name = _class.name
    comment = None
    functions = []
    attributes = []
    inheritance = None
    if _class.docstring:
        docstring = _class.docstring.parse('google')
        for section in docstring:
            if section.kind.value == 'text':
                comment = section.value.replace('->', '&#8594;') # Replace arrow characters
            elif section.kind.value == 'attributes':
                for attr in section.value:
                    attributes.append(get_attribute(attr, package))
    for _, function in _class.functions.items():
        functions.append(get_function(function, package))
    return Class(name, functions, attributes, comment, inheritance)

def generate_pyfile_docs():
    template_path = Path(__file__).parent / 'templates/'
    environment = Environment(loader=FileSystemLoader(str(template_path)), trim_blocks=True, lstrip_blocks=True)
    doc_template = environment.get_template('doc.md')
    for pkg in MODULES:
        package = griffe.load(pkg) 
        seen = set([])
        modules = deque([package])
        while modules:
            # Get package name
            mod = modules.popleft()
            module_name = mod.name
            if module_name in seen:
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
                            attributes.append(get_attribute(attr, package))
            
            functions = []
            classes = []
            # Iterate through functions
            for name, member in mod.members.items():
                if member.is_alias:
                    continue
                elif member.is_function:
                    functions.append(get_function(member, package))
                elif member.is_class:
                    classes.append(get_class(member, package))
                elif member.is_module:
                    modules.append(member)
            seen.add(module_name)
            module_object = Package(module_name, functions, attributes, classes, comment)
            output_rel_path = str(mod.relative_package_filepath).replace('.py', '.md')
            full_path = f'{OUTPUT_PATH}{output_rel_path}'
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'w') as f:
                f.write(doc_template.render(asdict(module_object)))

def generate_protobuf_docs():
    pass

generate_pyfile_docs()
