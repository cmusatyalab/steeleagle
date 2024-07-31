import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
from task_defs.Task import TaskArguments, TaskType


class MissionCreator:

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
        logger.info(f"MissionCreator: no matched up transition, triggered event {triggered_event}\n", triggered_event)
    #task
    @staticmethod
    def define_mission(transitMap, task_arg_map):
        #define transition
        logger.info("MissionCreator: define the transitMap\n")
        transitMap["start"] = MissionCreator.start_transit
        transitMap["tri"]= MissionCreator.tri_transit
        transitMap["default"]= MissionCreator.default_transit
        # define task
        logger.info("MissionCreator: define the tasks\n")
        # TASKtri
        task_attr_tri = {}
        task_attr_tri["gimbal_pitch"] = "-20.0"
        task_attr_tri["drone_rotation"] = "0.0"
        task_attr_tri["sample_rate"] = "2"
        task_attr_tri["hover_delay"] = "0"
        task_attr_tri["coords"] = "[{'lng': -79.9499065, 'lat': 40.4152976, 'alt': 15.0},{'lng': -79.9502364, 'lat': 40.4152976, 'alt': 15.0},{'lng': -79.950054, 'lat': 40.4151098, 'alt': 15.0},{'lng': -79.9499065, 'lat': 40.4152976, 'alt': 15.0}]"
        
        transition_attr_tri = {}
        
        task_arg_map["tri"] = TaskArguments(TaskType.Test, transition_attr_tri, task_attr_tri)
        logger.info("MissionCreator: finish defining the tasks\n")
