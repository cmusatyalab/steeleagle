import asyncio
from json import JSONDecodeError
import sys
import json
import numpy as np
import math
from project.implementation.transition_defs.TimerTransition import TimerTransition
from project.interface.Task import Task
import time
import logging
from gabriel_protocol import gabriel_pb2
from scipy.spatial.transform import Rotation as R

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class TrackTask(Task):

    def __init__(self, drone, cloudlet, task_id, trigger_event_queue, task_args):
        super().__init__(drone, cloudlet, task_id, trigger_event_queue, task_args)
        # TODO: Make this a drone interface command
        # self.image_res = drone.getResolution()
        self.image_res = (1280, 720)
        self.pixel_center = (self.image_res[0] / 2, self.image_res[1] / 2)
        # TODO: Make this a drone interface command
        # self.HFOV = drone.getFOV()[0]
        # self.VFOV = drone.getFOV()[1]
        self.HFOV = 69
        self.VFOV = 43
        self.target_lost_duration = 10

        # PID controller parameters
        # TODO: Somehow, this needs to be portable to other drones, maybe we implement a 
        # setpoint interface? This would be easy with MAVLINK drones but harder with the
        # ANAFI series.
        self.time_prev = None
        self.error_prev = [0, 0, 0]
        self.yaw_pid_info = {"constants": {"Kp": 10.0, "Ki": 0.09, "Kd": 40.0}, "saved" : {"I": 0.0}}
        self.move_pid_info = {"constants": {"Kp": 2.0, "Ki": 0.030, "Kd": 35.0}, "saved" : {"I": 0.0}}

    def create_transition(self):
        logger.info(self.transitions_attributes)
        args = {
            'task_id': self.task_id,
            'trans_active': self.trans_active,
            'trans_active_lock': self.trans_active_lock,
            'trigger_event_queue': self.trigger_event_queue
        }
        
        # Triggered event
        if ("timeout" in self.transitions_attributes):
            timer = TimerTransition(args, self.transitions_attributes["timeout"])
            timer.daemon = True
            timer.start()
    
    def targetBearing(self, origin, destination):
        lat1, lon1 = origin
        lat2, lon2 = destination

        rlat1 = math.radians(lat1)
        rlat2 = math.radians(lat2)
        rlon1 = math.radians(lon1)
        rlon2 = math.radians(lon2)
        dlon = math.radians(lon2-lon1)

        b = math.atan2(math.sin(dlon)*math.cos(rlat2),math.cos(rlat1)*math.sin(rlat2)-math.sin(rlat1)*math.cos(rlat2)*math.cos(dlon))
        bd = math.degrees(b)
        br,bn = divmod(bd+360,360)

        return bn

    def findIntersection(self, target_dir, target_insct):
        plane_pt = np.array([0, 0, 0])
        plane_norm = np.array([0, 0, 1])

        if plane_norm.dot(target_dir).all() == 0:
            return None

        t = (plane_norm.dot(plane_pt) - plane_norm.dot(target_insct)) / plane_norm.dot(target_dir)
        return target_insct + (t * target_dir)
    
    async def estimateDistance(self, yaw, pitch):
        alt = await self.drone.getRelAlt()
        gimbal = await self.drone.getGimbalPitch()

        vf = [0, 1, 0]
        r = R.from_euler('ZYX', [yaw, 0, pitch + gimbal], degrees=True)
        target_dir = r.as_matrix().dot(vf)
        target_vec = self.findIntersection(target_dir, np.array([0, 0, alt]))
        
        logger.info(f"[TrackTask]: Distance estimation: {np.linalg.norm(target_vec)}")
        leash_vec = self.leash_length * (target_vec / np.linalg.norm(target_vec))
        logger.info(f"[TrackTask]: Error vector length: {np.linalg.norm(leash_vec - target_vec)}")
        return leash_vec - target_vec

    async def error(self, box):
        target_x_pix = self.image_res[0] - int(((box[3] - box[1]) / 2.0) + box[1])
        target_y_pix = self.image_res[1] - int(((box[2] - box[0]) / 2.0) + box[0])
        target_yaw_angle = ((target_x_pix - self.pixel_center[0]) / self.pixel_center[0]) * (self.HFOV / 2)
        target_pitch_angle = ((target_y_pix - self.pixel_center[1]) / self.pixel_center[1]) * (self.VFOV / 2)
        target_bottom_pitch_angle = (((self.image_res[1] - box[2]) - self.pixel_center[1]) / self.pixel_center[1]) * (self.VFOV / 2)
        
        yaw_error = -1 * target_yaw_angle
        gimbal_error = target_pitch_angle
        move_error = await self.estimateDistance(target_yaw_angle, target_bottom_pitch_angle)
        
        return (yaw_error, gimbal_error, move_error[1] * -1)

    def clamp(self, value, minimum, maximum):
        return max(minimum, min(value, maximum))

    async def pid(self, box):
        error = await self.error(box)
        ye = error[0]
        ge = error[1]
        me = error[2]
        ts = round(time.time() * 1000)

        # Reset pid loop if we haven't seen a target for a second or this is
        # the first target we have seen.
        if self.time_prev is None or (ts - self.time_prev) > 1000:
            self.time_prev = ts - 1 # Do this to prevent a divide by zero error!
            self.error_prev = [ye, ge, me]

        # Control loop for yaw
        Py = self.yaw_pid_info["constants"]["Kp"] * ye
        Iy = self.yaw_pid_info["constants"]["Ki"] * (ts - self.time_prev)
        if ye < 0:
            Iy *= -1
        self.yaw_pid_info["saved"]["I"] += Iy
        self.yaw_pid_info["saved"]["I"] = self.clamp(self.yaw_pid_info["saved"]["I"], -100.0, 100.0)
        Dy = self.yaw_pid_info["constants"]["Kd"] * (ye - self.error_prev[0]) / (ts - self.time_prev)
        logger.info(f"[TrackTask]: YAW values {ye} {Py} {Iy} {Dy}")
        yaw = Py + Iy + Dy

        # Control loop for gimbal
        gimbal = ge * 0.5

        # Control loop for movement
        logger.info(f"[TrackTask]: Move error {me}")
        extra = 1.0
        if me < 0:
            extra = 2.5
        Pm = self.move_pid_info["constants"]["Kp"] * me * 2 * extra
        Im = self.move_pid_info["constants"]["Ki"] * (ts - self.time_prev) * extra
        if me < 0:
            Im *= -1
        self.move_pid_info["saved"]["I"] += Im * extra
        self.move_pid_info["saved"]["I"] = self.clamp(self.move_pid_info["saved"]["I"], -100.0, 100.0)
        Dm = self.move_pid_info["constants"]["Kd"] * (me - self.error_prev[2]) / (ts - self.time_prev)
        logger.info(f"[TrackTask]: MOVE values {me} {Pm} {Im} {Dm}")
        move = Pm + Im + Dm

        yaw = self.clamp(int(yaw), -100, 100)
        pitch = self.clamp(int(move), -100, 100)

        self.time_prev = ts
        self.error_prev = [ye, ge, me]

        return (yaw, gimbal, pitch)

    async def actuate(self, vels):
        #await self.drone.PCMD(0, vels[2], vels[0], 0)
        logger.info(f"Calling pcmd with {vels}")
        await self.drone.PCMD(0, vels[2], vels[0], 0)
        g = await self.drone.getGimbalPitch()
        await self.drone.setGimbalPose(0.0, g + float(vels[1]), 0.0)

    @Task.call_after_exit
    async def run(self):
        logger.info("[TrackTask]: Starting tracking task")

        self.cloudlet.switchModel(self.task_attributes["model"])
        self.cloudlet.setHSVFilter(lower_bound=self.task_attributes["lower_bound"], upper_bound=self.task_attributes["upper_bound"])
        
        # TODO: Parameterize this
        # self.leash_length = float(self.task_attributes["leash"])
        self.leash_length = 15.0
        logger.info(f"[TrackTask]: Setting leash length {self.leash_length}")

        target = self.task_attributes["class"]

        # TODO: This should only be done if requested.
        #await self.drone.setGimbalPose(0.0, float(self.task_attributes["gimbal_pitch"]), 0.0)

        self.create_transition()
        last_seen = None
        while True:
            result = self.cloudlet.getResults("openscout-object")
            if last_seen is not None and int(time.time() - last_seen)  > self.target_lost_duration:
                #if we have not found the target in N seconds trigger the done transition
                break
            if result != None:
                if result.payload_type == gabriel_pb2.TEXT:
                    try:
                        json_string = result.payload.decode('utf-8')
                        json_data = json.loads(json_string)
                        box = None
                        for det in json_data:

                            # Return the first instance found of the target class.
                            if det["class"] == target and det["hsv_filter"]:
                                box = det["box"]
                                last_seen = time.time()
                                break 

                        # Found an instance of target, start tracking!
                        if box is not None:
                            logger.info(f"[TrackTask]: Detected instance of {target}, tracking...")
                            vels = await self.pid(box)
                            await self.actuate(vels)
                    except JSONDecodeError as e:
                        logger.error(f"[TrackTask]: Error decoding json, ignoring")
                    except Exception as e:
                        exc_type, exc_obj, exc_tb = sys.exc_info()
                        logger.error(f"[TrackTask]: Exception encountered, {e}, line no {exc_tb.tb_lineno}")
            
            await asyncio.sleep(0.03)
       
