from pathlib import Path
from google.protobuf import descriptor_pb2

def get_descriptors():
    descriptor_file = Path(__file__).parent / 'protocol.desc'
    protocol_fds = descriptor_pb2.FileDescriptorSet()
    with open(str(descriptor_file), 'rb') as f:
        protocol_fds.MergeFromString(f.read())
    return protocol_fds
