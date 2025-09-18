# Protocol import
from steeleagle_sdk.protocol.services import compute_service_pb2_grpc as compute_proto
# Utility import
from steeleagle_sdk.protocol.rpc_helpers import generate_response
from util.log import get_logger

logger = get_logger('kernel/services/compute_service')

class ComputeService(compute_proto.ComputeServicer):
    '''
    Implementation of the compute service.
    '''
    def __init__(self):
        pass
