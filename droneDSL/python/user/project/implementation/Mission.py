import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
from user.project.interface.Task import TaskArguments, TaskType


class Mission:
    # transition
    @staticmethod
    def start_transit(triggered_event):
        logger.info("start_transit\n")
        return "dummy"
    @staticmethod
    def dummy_transit(triggered_event):
        if (triggered_event == "done"):
            return "terminate"

    @staticmethod
    def default_transit(triggered_event):
        logger.info(f"no matched up transition, triggered event {triggered_event}\n", triggered_event)
    #task
    @staticmethod
    def define_mission(transitMap, task_arg_map):
        #define transition
        logger.info("define the transitMap\n")
        transitMap["start"] = Mission.start_transit
        transitMap["dummy"]= Mission.dummy_transit
        transitMap["default"]= Mission.default_transit
        # define task
        logger.info("define the tasks\n")
        # TASKdummy
        task_attr_dummy = {}
        transition_attr_dummy = {}
        task_arg_map["dummy"] = TaskArguments(TaskType.Test, transition_attr_dummy, task_attr_dummy)
        logger.info("finish defining the tasks\n")
