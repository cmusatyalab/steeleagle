from enum import Enum
from cnc_protocol import cnc_pb2
from typing import Optional, Union
import logging

logger = logging.getLogger(__name__)

class DataStore:
    def __init__(self):
        # Raw data caches
        self._raw_data_cache = {
            cnc_pb2.Telemetry: None,
            cnc_pb2.Frame: None,
        }

        # Processed data cache dict
        self._result_cache = {}

    ######################################################## COMPUTE ############################################################
    def get_compute_result(self, compute_id, compute_type: str) -> Optional[Union[None, tuple]]:
        pass

    def append_compute(self, compute_id):
        self._result_cache[compute_id] = {}

    def update_compute_result(self, compute_id, compute_type: str, result, timestamp):
        assert isinstance(compute_type, str), f"Argument must be a string, got {type(compute_type).__name__}"
        self._result_cache[compute_id][compute_type] = (result, timestamp)
        logger.debug(f"update_compute_result: Updated result cache for compute {compute_id} with type {compute_type}; result: {result}")

    ######################################################## RAW DATA ############################################################
    def get_raw_data(self, data_copy):
        data_copy_type = type(data_copy)
        if data_copy_type not in self._raw_data_cache:
            # Log an error and return None
            logger.error(f"get_raw_data: No such data: data type {data_copy_type}")
            return None

        cache = self._raw_data_cache.get(data_copy_type)
        if cache is None:
            # Log an error and return None
            logger.error(f"get_raw_data: No data found for data type {data_copy_type}")
            return None

        # Create a copy of the protobuf message
        data_copy.CopyFrom(cache)

        # # Clear the cache
        # self._raw_data_cache[data_copy_type] = None


    def set_raw_data(self, data):
        data_type = type(data)
        if data_type not in self._raw_data_cache:
            logger.error(f"set_raw_data: No such data: data type {data_type}")
            return None

        self._raw_data_cache[data_type] = data

    def get_processed_data(self):
        pass

    def set_processed_data(self, data):
        pass
