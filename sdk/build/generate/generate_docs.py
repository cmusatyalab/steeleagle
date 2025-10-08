import griffe

_API_MODULE_PATH = '../../protocol'
_DSL_MODULE_PATH = '../../dsl'

def generate_pyfile_docs():
    # API Module Docs
    api = griffe.load(_API_MODULE_PATH) 
    for name, member in api.modules.items():
        print(name, member)
        if member.is_module:
            for n, m in member.modules.items():
                print(n)

def generate_protobuf_docs():
    pass

generate_pyfile_docs()
