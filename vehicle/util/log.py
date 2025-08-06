import grpc
# Utility import
from util.rpc import generate_request
from util.config import query_config
# Protocol import
from google.protobuf.json_format import MessageToDict
from python_bindings.flight_log_service_pb2 import LogRequest, LogMessage, LogType
from python_bindings.flight_log_service_pb2_grpc import FlightLogStub

class LogWrapper:
    '''
    Wraps over the log server stub to provide a Pythonic log interface.
    '''
    def __init__(self, topic):
        self._topic = topic
        self._channel = grpc.insecure_channel(query_config('internal.flight_log_service.endpoint'))
        self._stub = FlightLogStub(self._channel)

    def _send_log_request(self, log_type, message):
        request = LogRequest(
            request=generate_request(),
            topic=self._topic,
            log=LogMessage(
                    type=log_type,
                    msg=message
                )
        )
        return True if self._stub.Log(request).response.status == 2 else False

    def info(self, message):
        return self._send_log_request(LogType.INFO, message)

    def debug(self, message):
        return self._send_log_request(LogType.DEBUG, message)

    def warning(self, message):
        return self._send_log_request(LogType.WARNING, message)

    def error(self, message):
        return self._send_log_request(LogType.ERROR, message)

    def info_proto(self, message):
        return self._send_log_request(LogType.INFO, str(MessageToDict(message)))

    def __del__(self):
        self._channel.close()


def get_logger(topic):
    '''
    Returns a log wrapper object that will log to the provided topic.
    '''
    return LogWrapper(topic)
