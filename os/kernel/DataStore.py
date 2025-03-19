import asyncio
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

        self._raw_data_id = {
            cnc_pb2.Frame: -1,
            cnc_pb2.Telemetry: -1,
        }

        self._raw_data_event = {
            cnc_pb2.Frame: asyncio.Event(),
        }

        # Processed data cache dict
        self._result_cache = {}

    def clear_compute_result(self, compute_id):
        logger.info(f"clear_compute_result: Clearing result for compute {compute_id}")
        self._result_cache.pop(compute_id, None)
        
    ######################################################## COMPUTE ############################################################
    def get_compute_result(self, compute_id, result_type: str) -> Optional[Union[None, tuple]]:
        logger.info(f"get_compute_result: Getting result for compute {compute_id} with type {result_type}")
        logger.info(self._result_cache)
        if compute_id not in self._result_cache:
            # Log an error and return None
            logger.error(f"get_compute_result: No such compute: compute id {compute_id}")
            return None

        cache = self._result_cache.get(compute_id)
        if cache is None:
            # Log an error and return None
            logger.error(f"get_compute_result: No result found for compute {compute_id}")
            return None

        result = cache.get(result_type)
        if result is None:
            # Log an error and return None
            logger.error(f"get_compute_result: No result found for compute {compute_id} with type {result_type}")
            return None

        return result

    def append_compute(self, compute_id):
        self._result_cache[compute_id] = {}

    def update_compute_result(self, compute_id, result_type: str, result, timestamp):
        assert isinstance(result_type, str), f"Argument must be a string, got {type(result_type).__name__}"
        self._result_cache[compute_id][result_type] = (result, timestamp)
        logger.debug(f"update_compute_result: Updated result cache for compute {compute_id} with type {result_type}; result: {result}")

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
            logger.debug(f"get_raw_data: No data found for data type {data_copy_type}")
            return None

        # Create a copy of the protobuf message
        data_copy.CopyFrom(cache)
        
        return self._raw_data_id.get(data_copy_type)

    def set_raw_data(self, data, data_id = None):
        data_type = type(data)
        if data_type not in self._raw_data_cache:
            logger.error(f"set_raw_data: No such data: data type {data_type}")
            return None

        self._raw_data_cache[data_type] = data

        # frame data is updated
        if data_type in self._raw_data_event:
            self._raw_data_event[data_type].set()

        if data_id and data_type in self._raw_data_id:
            self._raw_data_id[data_type] = data_id

    async def wait_for_new_data(self, data_type):
        if data_type not in self._raw_data_event:
            logger.error(f"wait_for_new_data: Cannot wait for type {data_type}")
            return None
        self._raw_data_event[data_type].clear()
        await self._raw_data_event[data_type].wait()

