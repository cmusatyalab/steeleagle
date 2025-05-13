import asyncio
import logging
import interface.Task as taskitf
import project.task_defs.TrackTask as track
import project.task_defs.DetectTask as detect
import project.task_defs.AvoidTask as avoid
import project.task_defs.TestTask as test

logger = logging.getLogger(__name__)

class TaskManager:
    def __init__(self, drone, compute, transit_map, task_arg_map):
        self.trigger_event_queue = asyncio.Queue()
        self.drone = drone
        self.compute = compute
        self.transit_map = transit_map
        self.task_arg_map = task_arg_map
        self.currentTask = None
        self.taskCurrentCoroutine = None
        self.curr_task_id = None
        self.start_task_id = None

    def get_current_task(self):
        return self.curr_task_id

    def retrieve_next_task(self, current_task_id, triggered_event):
        logger.info(f"next task, current_task_id {current_task_id}, trigger_event {triggered_event}")
        try:
            next_task_id = self.transit_map.get(current_task_id)(triggered_event)
        except Exception as e:
            logger.error(f"Failed to retrieve next task: {e}")
            next_task_id = None

        logger.info(f"next_task_id {next_task_id}")
        return next_task_id

    async def stop_task(self):
        logger.info(f"Stopping current task {self.curr_task_id}")
        if self.currentTask:
            await self.currentTask.stop_trans()
            if self.taskCurrentCoroutine:
                self.taskCurrentCoroutine.cancel()
                try:
                    await self.taskCurrentCoroutine
                except asyncio.CancelledError:
                    logger.info(f"Task {self.curr_task_id} cancelled successfully")

            logger.info(f"Clearing currentTask reference for task_id {self.curr_task_id}")
            self.currentTask = None
            self.taskCurrentCoroutine = None
            self.curr_task_id = None

    async def start_task(self, task):
        logger.info(f"Starting task {task.task_id}")
        self.currentTask = task
        self.taskCurrentCoroutine = asyncio.create_task(task.run())
        self.curr_task_id = task.task_id

    def create_task(self, task_id):
        logger.info(f"Creating task with task_id {task_id}")
        if task_id in self.task_arg_map:
            task_args = self.task_arg_map[task_id]
            if task_args.task_type == taskitf.TaskType.Detect:
                return detect.DetectTask(self.drone, self.compute, task_id, self.trigger_event_queue, task_args)
            elif task_args.task_type == taskitf.TaskType.Track:
                return track.TrackTask(self.drone, self.compute, task_id, self.trigger_event_queue, task_args)
            elif task_args.task_type == taskitf.TaskType.Avoid:
                return avoid.AvoidTask(self.drone, self.compute, task_id, self.trigger_event_queue, task_args)
            elif task_args.task_type == taskitf.TaskType.Test:
                return test.TestTask(self.drone, self.compute, task_id, self.trigger_event_queue, task_args)
        logger.warning(f"No matching task found for task_id {task_id}")
        return None

    async def init_task(self):
        logger.info("Initializing start task")
        self.start_task_id = self.retrieve_next_task("start", None)
        if self.start_task_id:
            start_task = self.create_task(self.start_task_id)
            if start_task:
                await self.start_task(start_task)

    async def transit_task_to(self, task):
        logger.info(f"Transiting to task with task_id: {task.task_id}, current_task_id: {self.curr_task_id}")
        await self.stop_task()
        await self.start_task(task)

    async def run(self):
        try:
            logger.info("Starting TaskManager loop")
            await self.init_task()

            while True:
                task_id, trigger_event = await self.trigger_event_queue.get()
                logger.info(f"Triggered event: task_id {task_id}, event {trigger_event}")

                if task_id == self.get_current_task():
                    next_task_id = self.retrieve_next_task(task_id, trigger_event)
                    if next_task_id == "terminate":
                        logger.info("Terminating TaskManager loop")
                        break

                    next_task = self.create_task(next_task_id)
                    if next_task:
                        await self.transit_task_to(next_task)

        except Exception as e:
            logger.exception(f"Exception in TaskManager loop: {e}")
        finally:
            await self.stop_task()
            logger.info("TaskManager shutdown complete")
