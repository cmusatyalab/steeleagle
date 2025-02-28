import asyncio
import logging

logger = logging.getLogger(__name__)


class Service:
    def __init__(self):
        self.context = None
        self.tasks = []
        self.socks = []

    def register_context(self, context):
        self.context = context

    def register_socket(self, sock):
        self.socks.append(sock)

    def register_task(self, task):
        logger.info("registered a task")
        self.tasks.append(task)

    async def start(self):
        logger.info("service started")
        try:
            await asyncio.gather(*self.tasks)

        except Exception:
            await self.shutdown()

    async def shutdown(self):
        logger.info(f"{self.__class__.__name__}: Shutting down CommandService")
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
