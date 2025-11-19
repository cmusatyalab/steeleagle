import grpc
import asyncio
import logging
# Utility import
from steeleagle_sdk.protocol.rpc_helpers import generate_request
from util.config import query_config
# Protocol import
from google.protobuf.json_format import MessageToDict
from steeleagle_sdk.protocol.services.flight_log_service_pb2 import LogRequest, LogMessage, LogType
from steeleagle_sdk.protocol.services.flight_log_service_pb2_grpc import FlightLogStub

# Log level for protos, between info and warning
PROTO_LEVEL = logging.INFO + 5

'''
The following section is used to add the 'proto' log call to the
logging library. This way, users can log request/response Protobufs by
calling logger.proto(<proto>).
'''
def proto(self, message, *args, **kwargs):
    if self.isEnabledFor(PROTO_LEVEL):
        str_message = f'{message.DESCRIPTOR.name} | {MessageToDict(message)}'
        self._log(PROTO_LEVEL, str_message, args, **kwargs)

def root(message, *args, **kwargs):
    logging.log(PROTO_LEVEL, message, *args, **kwargs)

import logging
logging.addLevelName(PROTO_LEVEL, 'PROTO')
setattr(logging, 'PROTO', PROTO_LEVEL)
setattr(logging.getLoggerClass(), 'proto', proto)
setattr(logging, 'proto', root)

class ColorFormatter(logging.Formatter):
    '''
    Logging Formatter to add colors to log output.
    '''
    gray = "\x1b[90m"
    green = "\x1b[92m"
    blue = "\x1b[38;5;69m"
    yellow = "\x1b[93m"
    red = "\x1b[91m"
    pink = "\x1b[38;5;206m"
    reset = "\x1b[0m"
    time = "%(asctime)s ["
    level  = "%(levelname)s"
    message = "] %(name)s: %(message)s"

    # Format logs so that they are colored by level
    FORMATS = {
        logging.DEBUG: time + reset + gray + level + reset + message,
        logging.INFO: time + reset + green + level + reset + message,
        logging.PROTO: time + reset + blue + level + reset + message,
        logging.WARNING: time + reset + yellow + level + reset + message,
        logging.ERROR: time + reset + red + level + reset + message,
        logging.CRITICAL: time + reset + pink + level + reset + message
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

class FlightLogHandler(logging.Handler):
    '''
    Log handler for sending records to the log service and writing
    them to an MCAP file.
    '''
    def __init__(self, addr):
        logging.Handler.__init__(self)
        self._stub = FlightLogStub(grpc.insecure_channel(addr))

    def emit(self, record):
        try:
            log_type = getattr(LogType, record.levelname.upper())
            request = LogRequest(
                request=generate_request(),
                topic=record.name,
                log=LogMessage(
                    type=log_type,
                    msg=record.getMessage()
                )
            )
            self._stub.Log(request)
        except grpc.RpcError:
            pass
        except Exception:
            self.handleError(record)

def setup_logging():
    '''
    Sets up root logger. This only needs to be called once, and all future loggers
    built from Python logging will have the correct configuration in the current
    process.
    '''
    root_logger = logging.getLogger()
    if query_config('logging.generate_flight_log'): # Only send to the log service if it's running
        flight_log_handler = FlightLogHandler(query_config('internal.services.flight_log')) # MCAP handler
        root_logger.addHandler(flight_log_handler)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(ColorFormatter())
    root_logger.addHandler(console_handler)
    root_logger.setLevel(query_config('logging.log_level'))
