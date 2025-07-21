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
    def __init__(self, topic):
        config = query_config('logging')
        self._topic = topic
        self._console_logger = None
        self._mcap_logger = None
        if config['log_to_console']:
            self._console_logger = logging.getLogger(topic)
            self._setup_console_logging(config)
        if config['log_to_mcap']:
            # Create an mcap file with the current datetime
            fname = config['custom_filename']
            if fname == '':
                date_time = datetime.now().strftime("%Y-%m-%d-%H:%M:%S")
                name = query_config('driver.name')
                fname = name + '_' + date_time + '.mcap'
            f = open(config['file_path'] + fname, 'wb')
            self._mcap_logger = Writer(f)

    def info(self, message):
        if self._console_logger:
            self._console_logger.info(message)
        if self._mcap_logger:
            ts = round(time.time() * 1000)
            self._mcap_logger.write_message(
                topic=self._topic,
                message=InfoLog(msg=message),
                log_time=ts,
                publish_time=ts,
            )

    def debug(self, message):
        if self._console_logger:
            self._console_logger.debug(message)
        if self._mcap_logger:
            ts = round(time.time() * 1000)
            mcap_writer.write_message(
                topic=self._topic,
                message=DebugLog(msg=message),
                log_time=ts,
                publish_time=ts,
            )

    def warning(self, message):
        if self._console_logger:
            self._console_logger.warning(message)
        if self._mcap_logger:
            ts = round(time.time() * 1000)
            mcap_writer.write_message(
                topic=self._topic,
                message=WarningLog(msg=message),
                log_time=ts,
                publish_time=ts,
            )

    def error(self, message):
        if self._console_logger:
            self._console_logger.error(message)
        if self._mcap_logger:
            ts = round(time.time() * 1000)
            mcap_writer.write_message(
                topic=self._topic,
                message=ErrorLog(msg=message),
                log_time=ts,
                publish_time=ts,
            )

    def log_proto(self, proto):
        if self._console_logger:
            self._console_logger.info(MessageToDict(proto))
        if self._mcap_logger:
            ts = round(time.time() * 1000)
            # Get the publish timestamp
            pts = self._get_publish_ts(proto)
            if not pts:
                pts = ts
            mcap_writer.write_message(
                topic=self._topic,
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
                "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
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
