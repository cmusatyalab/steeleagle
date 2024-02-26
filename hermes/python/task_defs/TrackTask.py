import asyncio
from json import JSONDecodeError
import json
import numpy as np
from transition_defs.TransTimer import TransTimer
from interfaces.Task import Task
import time
import logging
from gabriel_protocol import gabriel_pb2
from scipy.spatial.transform import Rotation as R


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class TrackTask(Task):

    def __init__(self, drone, cloudlet, task_id, trigger_event_queue, task_args):
        super().__init__(drone, cloudlet, task_id, trigger_event_queue, task_args)
        self.leash = 6.0
        self.image_res = (1280, 720)
        self.pixel_center = (self.image_res[0] / 2, self.image_res[1] / 2)
        self.HFOV = 69
        self.VFOV = 43
        self.prev_center = None
        self.prev_center_ts = None
        self.hysteresis = True
        
    def create_transition(self):
        
        logger.info(f"**************Track Task {self.task_id}: create transition! **************\n")
        logger.info(self.transitions_attributes)
        args = {
            'task_id': self.task_id,
            'trans_active': self.trans_active,
            'trans_active_lock': self.trans_active_lock,
            'trigger_event_queue': self.trigger_event_queue
        }
        
        # triggered event
        if ("timeout" in self.transitions_attributes):
            logger.info(f"**************Track Task {self.task_id}:  timer transition! **************\n")
            timer = TransTimer(args, self.transitions_attributes["timeout"])
            timer.daemon = True
            timer.start()

            
    async def run(self):
        
        logger.info(f"**************Track Task {self.task_id}: hi this is Track task {self.task_id}**************\n")
        
        target = self.task_attributes["class"]
        
        await self.drone.setGimbalPose(0.0, float(self.task_attributes["gimbal_pitch"]), 0.0)
        
        self.cloudlet.switchModel(self.task_attributes["model"])
        
        self.create_transition()
        
        start = None
        counter = 0
        while True:
            # get result
            result = self.cloudlet.getResults("openscout-object")
            if (result != None):
                counter += 1
                if (start is not None):
                    logger.info(f"TRACKING FPS: {counter / (time.time() - start)}")
                logger.info(f"**************Track Task: {self.task_id}: detected payload! {result}**************\n")
                # Check if the payload type is TEXT, since  JSON seems to be text data
                if result.payload_type == gabriel_pb2.TEXT:
                    try:
                        # Decode the payload from bytes to string
                        json_string = result.payload.decode('utf-8')

                        # Parse the JSON string
                        json_data = json.loads(json_string)

                        # Access the 'class' attribute
                        class_attribute = json_data[0]['class']  # Adjust the indexing based on JSON structure
                        
                        logger.info(f"**************Track Task: detected class: {class_attribute}, target class: {target}**************")
                        
                        if (class_attribute == target):
                            start = time.time()
                            logger.info(f"**************Track Task: condition met, and execute tracking**************")
                            gimbal_pitch, drone_yaw, drone_pitch, drone_roll  = await self.calculate_offsets(json_data[0]["box"])
                            await self.execute_PCMD(gimbal_pitch, drone_yaw, drone_pitch, drone_roll)
                        
                        
                    except JSONDecodeError as e:
                        logger.error(f'Track Task: Error decoding json: {json_string}')
                    except Exception as e:
                        print(f"Track Task: Exception: {e}")
            await asyncio.sleep(0.1)



    def find_intersection(self, target_dir, target_insct):
        plane_pt = np.array([0, 0, 0])
        plane_norm = np.array([0, 0, 1])

        if plane_norm.dot(target_dir).all() == 0:
            return None

        t = (plane_norm.dot(plane_pt) - plane_norm.dot(target_insct)) / plane_norm.dot(target_dir)
        return target_insct + (t * target_dir)
    
    async def get_movement_vectors(self, yaw, pitch):
        current_drone_altitude = await self.drone.getRelAlt()
        current_gimbal_pitch = await self.drone.getGimbalPitch()
        
        
        forward_vec = [0, 1, 0]
        r = R.from_euler('ZYX', [yaw, 0, pitch + current_gimbal_pitch], degrees=True)
        target_dir = r.as_matrix().dot(forward_vec)
        target_vec = self.find_intersection(target_dir, np.array([0, 0, current_drone_altitude]))
        print(f"Distance estimate: {np.linalg.norm(target_vec)}")
        
        leash_vec = self.leash * (target_vec / np.linalg.norm(target_vec))
        print(f"Leash vector: {leash_vec}")
        movement_vec = target_vec - leash_vec
        print(f"Move vector: {movement_vec}")

        return movement_vec[0], movement_vec[1]

    async def calculate_offsets(self, box):
        print(f'Bounding box: {box}')
        #target_x_pix = int((((box[3] - box[1]) / 2.0) + box[1]) * self.image_res[0])
        #target_y_pix = int((1 - (((box[2] - box[0]) / 2.0) + box[0])) * self.image_res[1])
        target_x_pix = int(((box[3] - box[1]) / 2.0) + box[1])
        target_y_pix = int(((box[2] - box[0]) / 2.0) + box[1])
        print(f'Offsets: {target_x_pix}, {target_y_pix}')
        target_yaw_angle = ((target_x_pix - self.pixel_center[0]) / self.pixel_center[0]) * (self.HFOV / 2)
        target_pitch_angle = ((target_y_pix - self.pixel_center[1]) / self.pixel_center[1]) * (self.VFOV / 2)

        drone_roll, drone_pitch = await self.get_movement_vectors(target_yaw_angle, target_pitch_angle)

        if self.hysteresis and self.prev_center_ts != None and round(time.time() * 1000) - self.prev_center_ts < 500:
            hysteresis_yaw_angle = ((self.prev_center[0] - target_x_pix) / self.prev_center[0]) * (self.HFOV / 2)
            hysteresis_pitch_angle = ((self.prev_center[1] - target_y_pix) / self.prev_center[1]) * (self.VFOV / 2)
            target_yaw_angle += 0.90 * hysteresis_yaw_angle
            target_pitch_angle += 0.20 * hysteresis_pitch_angle
        
        self.prev_center_ts = round(time.time() * 1000)
        self.prev_center = (target_x_pix, target_y_pix)

        return target_pitch_angle, target_yaw_angle, drone_pitch, drone_roll

    def clamp(self, value, minimum, maximum):
        return max(minimum, min(value, maximum))

    def gain(self, gpitch, dyaw, dpitch, droll):
        dyaw = self.clamp(int(dyaw), -100, 100)
        dpitch = self.clamp(int(dpitch * 0.5), -100, 100)
        droll = self.clamp(int(droll * 0.5), -100, 100)
        gpitch = gpitch

        return gpitch, dyaw, dpitch, droll

    async def execute_PCMD(self, gpitch, dyaw, dpitch, droll):
        gpitch, dyaw, dpitch, droll = self.gain(gpitch, dyaw, dpitch, droll)
        print(f"Gimbal Pitch: {gpitch}, Drone Yaw: {dyaw}, Drone Pitch: {dpitch}, Drone Roll: {droll}")
        await self.drone.PCMD(0, 0, dyaw, 0)
        await self.drone.setGimbalPose(0.0, -float(gpitch), 0.0)