# from ..transition_defs.ObjectDetectionTransition import ObjectDetectionTransition
# from ..transition_defs.TimerTransition import TimerTransition
# from ..transition_defs.HSVDetectionTransition import HSVDetectionTransition
# from interface.Task import Task
# import asyncio
# import ast
# import logging
# from gabriel_protocol import gabriel_pb2


# logger = logging.getLogger(__name__)
# logger.setLevel(logging.INFO)

# class DetectTask(Task):

#     def __init__(self, control, data, task_id, trigger_event_queue, task_args):
#         super().__init__(control, data, task_id, trigger_event_queue, task_args)
#         self.first_wp_flag = True


#     async def create_transition(self):
#         logger.info(f"**************Detect Task {self.task_id}: creating transition! **************\n")
#         logger.info(f"**************Detect Task {self.task_id}: transition attributes: {self.transitions_attributes}**************\n")
#         args = {
#             'task_id': self.task_id,
#             'trans_active': self.trans_active,
#             'trans_active_lock': self.trans_active_lock,
#             'trigger_event_queue': self.trigger_event_queue
#         }
#         if ("object_detection" in self.transitions_attributes):
#             logger.info(f"**************Detect Task {self.task_id}:  object detection transition! **************\n")
#             object_trans = ObjectDetectionTransition(args, self.transitions_attributes["object_detection"], self.data)
#             object_trans.daemon = True
#             await object_trans.start()
#         logger.info(f"**************Detect Task {self.task_id}:  Finish creating transition! **************\n")

#     async def elevate(self, altitude):
#         logger.info(f"**************Detect Task {self.task_id}: elevate to {altitude}**************\n")
#         while True:
#             tel = await self.data.get_telemetry()
#             rel_alt = tel['relative_position']['up']

#             if tel["data_age_ms"] > 1000:
#                 logger.info("Received stale telemetry, hovering")
#                 await self.control['ctrl'].hover()
#                 continue

#             logger.info(f"**************Detect Task {self.task_id}: relative altitude: {rel_alt}**************\n")
#             if rel_alt > altitude:
#                 break
#             await self.control['ctrl'].set_velocity_body(0.0, 0.0, 1.0, 0.0)
#             await asyncio.sleep(1)
#         logger.info(f"**************Detect Task {self.task_id}: elevate done! **************\n")

#     async def prepatrol(self, elevation_alt):
#         logger.info(f"**************Detect Task {self.task_id}: prepatrol! **************\n")
#         await self.elevate(elevation_alt)

#         logger.info(f"**************Detect Task {self.task_id}: set gimbal pose! **************\n")
#         await self.control['ctrl'].set_gimbal_pose(float(self.task_attributes["gimbal_pitch"]), 0.0, 0.0)

#         logger.info(f"**************Detect Task {self.task_id}: prepatrol done! **************\n")


#     async def report(self, msg):
#         reply = await self.control['report'].send_notification(msg)
#         self.running_flag = reply['status']
#         self.patrol_areas = reply['patrol_areas']
#         self.altitude = reply['altitude']

#     @Task.call_after_exit
#     async def run(self):
#         logger.info(f"**************Detect Task {self.task_id}: hi this is detect task {self.task_id}**************\n")
#         # init the data
#         model = self.task_attributes["model"]
#         lower_bound = self.task_attributes["lower_bound"]
#         upper_bound = self.task_attributes["upper_bound"]
#         await self.control['ctrl'].configure_compute(model, lower_bound, upper_bound)

#         logger.info("Sending notification")
#         await self.report("start")
#         await self.prepatrol(self.altitude + 5)

#         logger.info(f"**************Detect Task {self.task_id}: running_flag: {self.running_flag}**************\n")
#         while self.running_flag == "running":
#             for area in self.patrol_areas:
#                 logger.info(f"**************Detect Task {self.task_id}: patrol area: {area}**************\n")
#                 coords = await self.control['report'].get_waypoints(area)
#                 for dest in coords:
#                     lng = dest["lng"]
#                     lat = dest["lat"]
#                     alt = self.altitude
#                     logger.info(f"**************Detect Task {self.task_id}: move to {lat}, {lng}, {alt}**************\n")
#                     await self.control['ctrl'].set_gps_location(lat, lng, alt, velocity=(3.0, 3.0, 90.0))

#                     # create the transition after the first waypoint
#                     if (self.first_wp_flag):
#                         await self.control['ctrl'].clear_compute_result("openscout-object")
#                         await self.create_transition()
#                         self.first_wp_flag = False

#                     await asyncio.sleep(1)
#             await self.report("finish")

#         logger.info(f"**************Detect Task {self.task_id}: Done**************\n")



