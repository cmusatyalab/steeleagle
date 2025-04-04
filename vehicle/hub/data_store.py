import asyncio
from dataclasses import dataclass
from google.protobuf import timestamp_pb2
from protocol import controlplane_pb2
from protocol import dataplane_pb2
from typing import Optional
import logging

logger = logging.getLogger(__name__)

@dataclass
class ComputeResult:
    """Class representing a compute result"""
    data: str
    frame_id: int
    timestamp: timestamp_pb2.Timestamp

class DataStore:
    def __init__(self):
        # Raw data caches
        self._raw_data_cache = {
            dataplane_pb2.Frame: None,
            dataplane_pb2.Telemetry: None,
        }

        self._raw_data_id = {
            dataplane_pb2.Frame: -1,
            dataplane_pb2.Telemetry: -1,
        }

        self._raw_data_event = {
            dataplane_pb2.Frame: asyncio.Event(),
        }

        # Processed data cache dict
        self._result_cache = {}

    def clear_compute_result(self, compute_id):
        logger.info(f"clear_compute_result: Clearing result for compute {compute_id}")
        self._result_cache.pop(compute_id, None)

    ######################################################## COMPUTE ############################################################
    def get_compute_result(self, compute_id, key) -> Optional[ComputeResult]:
        logger.info(f"get_compute_result: Getting result for compute {compute_id} with type {key}")
        logger.info(self._result_cache)
        if compute_id not in self._result_cache:
            # Log an error and return None
            logger.error(f"get_compute_result: No such compute: {compute_id=}")
            return None

        cache = self._result_cache.get(compute_id)
        if cache is None:
            # Log an error and return None
            logger.error(f"get_compute_result: No result found for {compute_id=}")
            return None

        result = cache.get(key)
        if result is None:
            # Log an error and return None
            logger.error(f"get_compute_result: No result found for {compute_id=} and {key=}")
            return None

        return result

    def append_compute(self, compute_id):
        self._result_cache[compute_id] = {}

    def update_compute_result(self, compute_id, key: str, result, frame_id, timestamp):
        assert isinstance(key, str), f"Argument must be a string, got {type(key).__name__}"
        self._result_cache[compute_id][key] = ComputeResult(result, frame_id, timestamp)
        logger.debug(f"update_compute_result: Updated result cache for {compute_id=} and {key=}; result: {result}")

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

