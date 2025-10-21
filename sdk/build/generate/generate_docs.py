import griffe
from griffe import Alias, ExprName, ExprSubscript, ExprTuple, ExprAttribute
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
        return ', '.join([resolve_annotation(item, module) for item in annotation])
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
    doc_template = environment.get_template('doc.md')
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

generate_pyfile_docs()
