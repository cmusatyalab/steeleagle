import asyncio
import importlib
import logging
import os
import shutil
import subprocess
import sys
from zipfile import ZipFile

import common_pb2 as common_protocol
import controlplane_pb2 as control_protocol
import requests
import zmq
from system_call_stubs.control_stub import ControlStub
from system_call_stubs.data_stub import DataStub
from system_call_stubs.report_stub import ReportStub
from util.utils import SocketOperation, setup_socket

logger = logging.getLogger(__name__)
context = zmq.Context()
msn_control_sock = context.socket(zmq.REP)
setup_socket(
    msn_control_sock, SocketOperation.CONNECT, "hub.network.controlplane.hub_to_mission"
)


class MissionController:
    def __init__(self, user_path):
        self.isTerminated = False
        self.tm = None
        self.transitMap = {}
        self.task_arg_map = {}
        self.current_task = None
        self.reload = False
        self.user_path = user_path
        self.msn_control_sock = msn_control_sock
        self.ctrl = {"drone": None, "report": None}

    ######################################################## MISSION ############################################################
    def install_prereqs(self) -> bool:
        ret = False
        # Pip install prerequisites for flight script
        requirements_path = os.path.join(self.user_path, "requirements.txt")
        try:
            subprocess.check_call(
                ["python3", "-m", "pip", "install", "-r", requirements_path]
            )
            ret = True
        except subprocess.CalledProcessError as e:
            logger.debug(f"Error pip installing requirements.txt: {e}")
        return ret

    def clean_user_path(self):
        for filename in os.listdir(self.user_path):
            file_path = os.path.join(self.user_path, filename)
            if os.path.isdir(file_path):
                shutil.rmtree(file_path)  # Remove directories
            else:
                os.remove(file_path)  # Remove files

    def download_script(self, url):
        # Download zipfile and extract reqs/flight script from cloudlet
        try:
            filename = url.rsplit(sep="/")[-1]
            logger.info(f"Writing {filename} to disk...")

            # Download the file
            r = requests.get(url, stream=True)
            r.raise_for_status()  # Raise an error for bad responses

            with open(filename, mode="wb") as f:
                for chunk in r.iter_content(chunk_size=8192):  # Use a chunk size
                    f.write(chunk)

            # Open the zip file
            with ZipFile(filename) as z:
                # Check if the path exists and remove it
                if os.path.exists(self.user_path):
                    logger.info(f"Removing old implementation at {self.user_path}")
                    self.clean_user_path()
                else:
                    logger.info(f"{self.user_path} does not exist. No need to remove")

                logger.info(f"Extracting {filename} to {self.user_path}")
                z.extractall(path=self.user_path)

            logger.info(f"Downloaded and extracted {filename} to {self.user_path}")
            self.install_prereqs()

        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")

    def download_mission(self, url):
        self.download_script(url)

    def reload_mission(self):
        logger.info("Reloading...")
        modules = sys.modules.copy()
        for module_name, module in modules.items():
            logger.info(f"Module name: {module_name}")
            if (
                module_name.startswith("project.task_defs")
                or module_name.startswith("project.Mission")
                or module_name.startswith("project.transition_defs")
            ):
                try:
                    # Log and reload the module
                    logger.info(f"Reloading module: {module_name}")
                    importlib.reload(module)
                except Exception as e:
                    logger.error(f"Failed to reload module {module_name}: {e}")

    def start_mission(self):
        if self.tm:
            logger.info("mission already running")
            return
        else:  # first time mission, create a task manager
            import core.TaskManager as tm

        logger.info("start the mission")
        if self.reload:
            self.reload_mission()

        import project.Mission as msn  # import the mission module instead of attribute of the module for the reload to work

        self.reload = True

        msn.Mission.define_mission(self.transitMap, self.task_arg_map)

        # start the tm
        logger.info("start the task manager")
        self.tm = tm.TaskManager(
            self.ctrl, self.data, self.transitMap, self.task_arg_map
        )
        self.tm_coroutine = asyncio.create_task(self.tm.run())

    async def end_mission(self):
        if self.tm and not self.tm_coroutine.cancelled():
            self.tm_coroutine.cancel()
            try:
                await self.tm_coroutine
            except asyncio.CancelledError:
                logger.info("Mission coroutine was cancelled successfully.")
            except Exception as e:
                logger.error(f"An error occurred while ending the mission: {e}")
            finally:
                self.tm = None
                self.tm_coroutine = None
                self.current_task = None
                logger.info("Mission has been ended and cleaned up.")
        else:
            logger.info("Mission not running or already cancelled.")

    ######################################################## MAIN LOOP ############################################################
    async def run(self):
        self.ctrl["ctrl"] = ControlStub()
        self.ctrl["report"] = ReportStub(self.user_path)
        self.data = DataStub()
        asyncio.create_task(self.ctrl["ctrl"].run())
        asyncio.create_task(self.data.run())
        asyncio.create_task(self.ctrl["report"].run())
        while True:
            try:
                # Mission task, not flight status
                if self.tm:
                    self.current_task = self.tm.get_current_task_type()
                else:
                    self.current_task = "idle"

                # Receive a message
                message = self.msn_control_sock.recv(flags=zmq.NOBLOCK)

                # Log the raw received message
                logger.info(f"Received raw message: {message}")

                # Parse the message
                req = control_protocol.Request()
                req.ParseFromString(message)
                seq_num = req.seq_num
                if not req.HasField("msn"):
                    logger.info("Received message without mission field, ignoring")
                    return

                msn_action = req.msn.action
                logger.info(f"Received message with action: {msn_action}")

                if msn_action == control_protocol.MissionAction.DOWNLOAD:
                    url = req.msn.url
                    self.download_mission(url)
                    resp = common_protocol.ResponseStatus.COMPLETED

                elif msn_action == control_protocol.MissionAction.START:
                    self.start_mission()
                    resp = common_protocol.ResponseStatus.COMPLETED

                elif msn_action == control_protocol.MissionAction.STOP:
                    await self.end_mission()
                    resp = common_protocol.ResponseStatus.COMPLETED

                else:
                    resp = common_protocol.ResponseStatus.NOTSUPPORTED

                # Send a reply back to the client
                rep = control_protocol.Response()
                rep.resp = resp
                rep.timestamp.GetCurrentTime()
                rep.seq_num = seq_num

                self.msn_control_sock.send(rep.SerializeToString())
            except zmq.Again:
                pass
            except Exception as e:
                logger.error(f"Failed to parse message: {e}")
                resp = common_protocol.ResponseStatus.FAILED

                # Send a reply back to the client
                rep = control_protocol.Response()
                rep.resp = resp
                rep.timestamp.GetCurrentTime()
                rep.seq_num = seq_num

                self.msn_control_sock.send(rep.SerializeToString())

            await asyncio.sleep(0)
