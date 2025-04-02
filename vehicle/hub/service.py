from abc import ABC
import asyncio
import logging
from util.utils import setup_socket
import zmq
import zmq.asyncio

logger = logging.getLogger(__name__)

class Service(ABC):
    def __init__(self):
        self.tasks = []
        self.socks = []
        self.create_asyncio_context()
        self.context = zmq.asyncio.Context()

    def register_socket(self, sock):
        self.socks.append(sock)

    def create_task(self, coro):
        task = asyncio.create_task(coro)
        self.tasks.append(task)

    def setup_and_register_socket(socket, socket_op, port_num, logger_message, host_addr="*"):
        setup_socket(socket, socket_op, port_num, logger_message, host_addr)
        self.socks.append(socket)

    async def start(self):
        logger.info(f'service started')
        try:
            await asyncio.gather(*self.tasks)

        except Exception:
            await self.shutdown()

    async def shutdown(self):
        logger.info(f'{self.__class__.__name__}: Shutting down CommandService')
        for sock in self.socks:
            sock.close()

        self.context.term()

        for task in self.tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            else:
                try:
                    task.result()
                except asyncio.CancelledError:
                    pass
                except Exception as err:
                    logger.error(f"Task raised exception: {err}")


        logger.info("Main: CommandService shutdown complete")



