import asyncio
from dataclasses import dataclass
from google.protobuf import timestamp_pb2
import dataplane_pb2 as data_protocol
from typing import Optional, Union
import time
import logging

logger = logging.getLogger(__name__)

@dataclass
class ComputeResult:
    """Class representing a compute result"""
    data: str
    frame_id: int
    timestamp: timestamp_pb2.Timestamp

@dataclass
class RawDataEntry:
    """Class representing raw data entries"""
    data: Union[data_protocol.Frame, data_protocol.Telemetry, None]
    data_id: Optional[int]
    timestamp: float

class DataStore:
    def __init__(self):
        # Raw data caches
        self._raw_data_cache = {
            data_protocol.Frame: None,
            data_protocol.Telemetry: None,
        }

        self._raw_data_event = {
            data_protocol.Frame: asyncio.Event(),
        }

        # Processed data cache dict
        self._result_cache = {}

    def clear_compute_result(self, compute_id):
        logger.info(f"clear_compute_result: Clearing result for compute {compute_id}")
        self._result_cache.pop(compute_id, None)

    ###########################################################################
    #                               COMPUTE                                   #
    ###########################################################################
    def get_compute_result(self, compute_id, type) -> Optional[ComputeResult]:
        logger.info(f"get_compute_result: Getting result for compute {compute_id} with type {type}")
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

        result = cache.get(type)
        if result is None:
            # Log an error and return None
            logger.error(f"get_compute_result: No result found for {compute_id=} and {type=}")
            return None

        return result

    def append_compute(self, compute_id):
        self._result_cache[compute_id] = {}

    def update_compute_result(self, compute_id, type: str, result, frame_id, timestamp):
        assert isinstance(type, str), f"Argument must be a string, got {type(type).__name__}"
        self._result_cache[compute_id][type] = ComputeResult(result, frame_id, timestamp)
        logger.debug(f"update_compute_result: Updated result cache for {compute_id=} and {type=}; result: {result}")

    ###########################################################################
    #                                RAW DATA                                 #
    ###########################################################################
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
        data_copy.CopyFrom(cache.data)

        return cache

    def set_raw_data(self, data, data_id = None):
        data_type = type(data)

        if data_type not in self._raw_data_cache:
            logger.error(f"set_raw_data: No such data: data type {data_type}")
            return None

        if self._raw_data_cache[data_type] is None:
            self._raw_data_cache[data_type] = RawDataEntry(data, data_id, time.monotonic())

        entry = self._raw_data_cache[data_type]

        entry.data = data
        entry.data_id = data_id
        entry.timestamp = time.monotonic()
        if data_type in self._raw_data_event:
            self._raw_data_event[data_type].set()

    async def wait_for_new_data(self, data_type):
        if data_type not in self._raw_data_event:
            logger.error(f"wait_for_new_data: Cannot wait for type {data_type}")
            return None
        self._raw_data_event[data_type].clear()
        await self._raw_data_event[data_type].wait()

