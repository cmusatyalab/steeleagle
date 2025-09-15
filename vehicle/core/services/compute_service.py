# Protocol import
from steeleagle_sdk.protocol.services import compute_service_pb2_grpc as compute_proto
# Utility import
from util.rpc import generate_response
from util.log import get_logger

logger = get_logger('core/services/compute_service')

class ComputeService(compute_proto.ComputeServicer):
    '''
    Implementation of the compute service.
    '''
    def __init__(self):
        pass
