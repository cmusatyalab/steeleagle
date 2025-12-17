import time

# MCAP import
from mcap_protobuf.writer import Writer

# Utility import
from util.config import query_config
from steeleagle_sdk.protocol.rpc_helpers import generate_response

# Protocol import
from steeleagle_sdk.protocol.services.flight_log_service_pb2_grpc import (
    FlightLogServicer,
)


class FlightLogService(FlightLogServicer):
    """
    Handles all logging for the system, and writes log files
    to a specified log directory.
    """

    def __init__(self, filename):
        self._mcap_logger = None
        log_config = query_config("logging")
        # Get path relative to vehicle directory
        self._file = open(filename, "wb")
        self._mcap_logger = Writer(self._file)
        print("Logger attached!")

    def _get_publish_ts(self, proto):
        """
        Gets a timestamp from the request object to get an
        accurate publish timestamp.
        """
        ts = proto.request.timestamp
        return round((ts.seconds + ts.nanos / 1e9) * 1000)

    def _log_to_mcap(self, request, content):
        ts = round(time.time() * 1000)
        self._mcap_logger.write_message(
            topic=request.topic,
            message=content,
            log_time=ts,
            publish_time=self._get_publish_ts(request),
        )

    def Log(self, request, context):
        self._log_to_mcap(request, request.log)
        return generate_response(2)

    def LogProto(self, request, context):
        message = request.reqrep_proto
        self._log_to_mcap(request, message)
        return generate_response(2)

    def cleanup(self):
        # Make sure we clean up the MCAP log so it is written to disk
        self._mcap_logger.finish()
        self._file.close()
        print(f"Logger exited, logs written to: {self._file.name}")
