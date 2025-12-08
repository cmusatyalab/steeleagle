#!/usr/bin/env python3
import asyncio
import contextlib
import logging
from typing import Optional

import grpc

from steeleagle_sdk.api.vehicle import Vehicle
from steeleagle_sdk.api.compute import Compute
from steeleagle_sdk.api.mission_store import MissionStore
from .fsm import MissionFSM
from steeleagle_sdk.dsl.compiler.ir import MissionIR
from steeleagle_sdk.dsl import types

logger = logging.getLogger(__name__)

# ---- Module-scoped runtime state ----
_CHANNEL: Optional[grpc.aio.Channel] = None
_STORE: Optional[MissionStore] = None
_FSM: Optional[MissionFSM] = None
_FSM_TASK: Optional[asyncio.Task] = None
_STARTED: bool = False
_LOCK = asyncio.Lock()


async def init(
    mission: MissionIR,
    vehicle_address: str,
    telemetry_address: str,
    result_address: str,
    map_obj,
) -> None:
    """
    Initialize runtime singletons and start the MissionFSM loop.
    Safe to call multiple times — subsequent calls are ignored.
    """
    global _CHANNEL, _STORE, _FSM, _FSM_TASK, _STARTED

    async with _LOCK:
        if _STARTED:
            logger.warning("Runtime already started; skipping re-init.")
            return

        logger.info("Starting runtime...")
        try:
            _CHANNEL = grpc.aio.insecure_channel(vehicle_address)

            _STORE = MissionStore(telemetry_address, result_address)
            await _STORE.start()
            logger.info("MissionStore started (telemetry=%s, results=%s).",
                        telemetry_address, result_address)

            veh = Vehicle(_CHANNEL, _STORE)
            cpt = Compute(_CHANNEL, _STORE)
            
            types.VEHICLE = veh
            types.COMPUTE = cpt
            types.MAP = map_obj

            _FSM = MissionFSM(mission)
            _FSM_TASK = asyncio.create_task(_FSM.start(), name="mission_fsm")
            _STARTED = True

            logger.info("Runtime started successfully (vehicle=%s).", vehicle_address)

        except Exception:
            logger.exception("Runtime failed to start; cleaning up partial init.")
            with contextlib.suppress(Exception):
                if _STORE:
                    await _STORE.stop()
            with contextlib.suppress(Exception):
                if _CHANNEL:
                    await _CHANNEL.close()

            _CHANNEL = _STORE = _FSM = _FSM_TASK = None
            _STARTED = False
            raise


async def term() -> None:
    """
    Stop the FSM task, shut down streams, and close the gRPC channel.
    Safe to call multiple times.
    """
    global _CHANNEL, _STORE, _FSM, _FSM_TASK, _STARTED

    async with _LOCK:
        if not _STARTED:
            logger.info("Runtime not started; nothing to stop.")
            return

        logger.info("Stopping runtime...")

        if _FSM_TASK and not _FSM_TASK.done():
            _FSM_TASK.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await _FSM_TASK
        _FSM_TASK = None
        _FSM = None

        if _STORE:
            try:
                await _STORE.stop()
            except Exception:
                logger.exception("Error stopping MissionStore")
        _STORE = None

        if _CHANNEL:
            try:
                await _CHANNEL.close()
            except Exception:
                logger.exception("Error closing gRPC channel")
        _CHANNEL = None

        _STARTED = False

        logger.info("Runtime stopped cleanly.")
