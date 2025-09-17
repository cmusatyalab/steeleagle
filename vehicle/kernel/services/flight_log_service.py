import os
import time
import logging
from datetime import datetime, timezone
from concurrent import futures
# MCAP import
from mcap_protobuf.writer import Writer
# Utility import
from util.config import query_config
from util.rpc import generate_response
# Protocol import
from steeleagle_sdk.protocol.services.flight_log_service_pb2_grpc import FlightLogServicer, add_FlightLogServicer_to_server
from steeleagle_sdk.protocol.services import flight_log_service_pb2 as log_proto

class ColorFormatter(logging.Formatter):
    '''
    Logging Formatter to add colors to log output.
    '''
    gray = "\x1b[90m"
    green = "\x1b[92m"
    yellow = "\x1b[93m"
    red = "\x1b[91m"
    reset = "\x1b[0m"
    time = "%(asctime)s ["
    level  = "%(levelname)s"
    message = "] %(message)s"

    # Format logs so that they are colored by level
    FORMATS = {
        logging.DEBUG: time + reset + gray + level + reset + message,
        logging.INFO: time + reset + green + level + reset + message,
        logging.WARNING: time + reset + yellow + level + reset + message,
        logging.ERROR: time + reset + red + level + reset + message,
        logging.CRITICAL: time + reset + red + level + reset + message
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

class FlightLogService(FlightLogServicer):
    '''
    Handles all logging for the system, and writes log files
    to a specified log directory.
    '''
    def __init__(self):
        self._mcap_logger = None
        self._console_logger = None
        log_config = query_config('logging')
        if log_config['generate_flight_log']:
            # Create an mcap file with the current datetime
            filename = log_config['custom_filename']
            if not filename:
                date_time = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H:%M:%S")
                name = query_config('vehicle.name')
                filename = name + '_' + date_time + '.mcap'
            try:
                from pathlib import Path
                # Get path relative to vehicle directory
                log_path = Path(__file__).parent / '../..' / log_config['file_path'] / filename
                self._file = open(str(log_path), 'wb')
            except:
                raise ValueError(
                        f'Could not open log file {filename}! Make sure your log path is set correctly.'
                        )
            self._mcap_logger = Writer(self._file)
        if log_config['log_to_console']:
            self._console_logger = logging.getLogger(__name__)
            self._setup_console_logging(log_config['log_level'])
    
    def _setup_console_logging(self, level):
        '''
        Build a console logger from provided level.
        '''
        # Set the log level
        if level != '':
            logging.basicConfig(level=level)
        else:
            # If no logging config exists, default to INFO
            logging.basicConfig(level='INFO')
        handler = logging.getLogger().handlers[0]
        handler.setFormatter(ColorFormatter())
    
    def _get_publish_ts(self, proto):
        '''
        Gets a timestamp from the request object to get an 
        accurate publish timestamp.
        '''
        ts = proto.request.timestamp
        return round((ts.seconds + ts.nanos / 1e9) * 1000)

    def _log_to_mcap(self, request, content):
        ts = round(time.time() * 1000)
        self._mcap_logger.write_message(
            topic=request.topic,
            message=content,
            log_time=ts,
            publish_time=self._get_publish_ts(request)
        )

    def Log(self, request, context):
        if self._console_logger:
            match request.log.type:
                case log_proto.LogType.INFO:
                    self._console_logger.info(
                            f"{request.topic} - {request.log.msg}"
                            )
                case log_proto.LogType.DEBUG:
                    self._console_logger.debug(
                            f"{request.topic} - {request.log.msg}"
                            )
                case log_proto.LogType.WARNING:
                    self._console_logger.warning(
                            f"{request.topic} - {request.log.msg}"
                            )
                case log_proto.LogType.ERROR:
                    self._console_logger.error(
                            f"{request.topic} - {request.log.msg}"
                            )
        if self._mcap_logger:
            self._log_to_mcap(request, request.log)
        return generate_response(2)

    def LogProto(self, request, context):
        message = request.reqrep_proto
        if self._console_logger:
            self._console_logger.info(
                    f'{request.topic} - {message.name} | {message.content}'
                    )
        if self._mcap_logger:
            self._log_to_mcap(request, message)
        return generate_response(2)

    def __del__(self):
        # Make sure we clean up the MCAP log so it is written to disk
        if self._mcap_logger:
            self._console_logger.info(f"Flight log written: {self._file.name}")
            self._mcap_logger.finish()
            self._file.close()
