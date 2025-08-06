import sys
import importlib
import os

# Import all the proto modules for this project
try:
    protos = os.listdir(os.getenv('PROTOSPATH'))
except:
    raise ValueError(f'Could not read protos in path: {PATH}; \
            are you sure you have the right path?')
for proto in protos:
    try:
        importlib.import_module(proto)
    except:
        pass

def read_any(any_obj):
    type_url = any_obj.type_url
    _, module, name = type_url.rsplit('.', 2)
    full = module + '_pb2'
    try:
        wrapper = getattr(sys.modules[full], name)()
        any_obj.Unpack(wrapper)
        return wrapper
    except Exception as e:
        raise ValueError(f"Could not read Any proto, reason {e}")
