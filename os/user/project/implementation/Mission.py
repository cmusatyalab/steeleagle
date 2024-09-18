import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
from project.interface.Task import TaskArguments, TaskType


class Mission:

    # transition
    @staticmethod
    def start_transit(triggered_event):
        logger.info("start_transit\n")
        return "tri"
    @staticmethod
    def tri_transit(triggered_event):
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
        transitMap["tri"]= Mission.tri_transit
        transitMap["default"]= Mission.default_transit
        # define task
        logger.info("define the tasks\n")
        # TASKtri
        task_attr_tri = {}
        transition_attr_tri = {}
        task_arg_map["tri"] = TaskArguments(TaskType.Test, transition_attr_tri, task_attr_tri)
        logger.info("finish defining the tasks\n")
