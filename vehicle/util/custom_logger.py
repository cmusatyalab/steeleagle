import logging
import os
import time
from datetime import datetime
# MCAP import
from mcap_protobuf.writer import Writer
# Utility import
from util.config import query_config
# Protocol import
from python_bindings.log_pb2 import InfoLog, DebugLog, WarningLog, ErrorLog
from google.protobuf.json_format import MessageToDict

class CustomLogger:
    '''
    Logger class that handles writing to MCAP files and creating
    console logs.
    '''
    def __init__(self):
        config = query_config('logging')
        self._console_logger = None
        self._mcap_logger = None
        if config['log_to_console']:
            self._console_logger = logging.getLogger(__name__)
            self._setup_console_logging(config)
        if config['log_to_mcap']:
            # Create an mcap file with the current datetime
            fname = config['custom_filename']
            if fname == '':
                date_time = datetime.now().strftime("%Y-%m-%d-%H:%M:%S")
                name = query_config('vehicle.name')
                fname = name + '_' + date_time + '.mcap'
            f = open(config['file_path'] + fname, 'wb')
            self._mcap_logger = Writer(f)
    
    class LogWrapper:
        '''
        Wrapper class so one CustomLogger instance is maintained.
        This makes sure finish() for the MCAP file is only called
        once upon deletion.
        '''
        def __init__(self, logger, topic):
            self._logger = logger
            self._topic = topic

        def info(self, message):
            self._logger.info(message, self._topic)

        def debug(self, message):
            self._logger.debug(message, self._topic)

        def warning(self, message):
            self._logger.warning(message, self._topic)

        def error(self, message):
            self._logger.error(message, self._topic)

        def log_proto(self, proto):
            self._logger.log_proto(message, self._topic)

    def get_logger(self, topic):
        return CustomLogger.LogWrapper(self, topic)

    def info(self, message, topic):
        if self._console_logger:
            self._console_logger.info(f"{topic} - {message}")
        if self._mcap_logger:
            ts = round(time.time() * 1000)
            self._mcap_logger.write_message(
                topic=topic,
                message=InfoLog(msg=message),
                log_time=ts,
                publish_time=ts,
            )

    def debug(self, message, topic):
        if self._console_logger:
            self._console_logger.debug(f"{topic} - {message}")
        if self._mcap_logger:
            ts = round(time.time() * 1000)
            mcap_writer.write_message(
                topic=topic,
                message=DebugLog(msg=message),
                log_time=ts,
                publish_time=ts,
            )

    def warning(self, message, topic):
        if self._console_logger:
            self._console_logger.warning(f"{topic} - {message}")
        if self._mcap_logger:
            ts = round(time.time() * 1000)
            mcap_writer.write_message(
                topic=topic,
                message=WarningLog(msg=message),
                log_time=ts,
                publish_time=ts,
            )

    def error(self, message, topic):
        if self._console_logger:
            self._console_logger.error(f"{topic} - {message}")
        if self._mcap_logger:
            ts = round(time.time() * 1000)
            mcap_writer.write_message(
                topic=topic,
                message=ErrorLog(msg=message),
                log_time=ts,
                publish_time=ts,
            )

    def log_proto(self, proto, topic):
        if self._console_logger:
            self._console_logger.info(f"{topic} - {MessageToDict(proto)}")
        if self._mcap_logger:
            ts = round(time.time() * 1000)
            # Get the publish timestamp
            pts = self._get_publish_ts(proto)
            if not pts:
                pts = ts
            mcap_writer.write_message(
                topic=topic,
                message=proto,
                log_time=ts,
                publish_time=pts,
            )
    
    def _get_publish_ts(self, proto):
        '''
        Tries to get a timestamp from the request of response
        object to get an accurate publish timestamp.
        '''
        try:
            ts = proto.request.timestamp
            return round((ts.seconds + ts.nanos / 1e9) * 1000)
        except:
            pass
        try:
            ts = proto.response.timestamp
            return round((ts.seconds + ts.nanos / 1e9) * 1000)
        except:
            pass
        return None


    def _setup_console_logging(self, config):
        '''
        Build a console logger from the config.
        '''
        logging_format = \
                "%(asctime)s [%(levelname)s] %(message)s"
        # Set the log level
        if config['log_level'] != '':
            logging.basicConfig(
                    level=config['log_level'],
                    format=logging_format,
                    force=True
                    )
        else:
            # If no logging config exists, default to INFO
            logging.basicConfig(level='INFO', format=logging_format)

    def __del__(self):
        if self._mcap_logger:
            self._mcap_logger.finish()
