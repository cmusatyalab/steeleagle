import olympe
from olympe.messages.ardrone3.Piloting import PCMD
from olympe.messages.ardrone3.PilotingState import AltitudeChanged
from olympe.messages.gimbal import set_target, attitude
from olympe.enums.gimbal import control_mode
import threading
import time
import zmq
import json


class DynamicLeashTracker(threading.Thread):
    def __init__(self, drone, leash=10):
        self.drone = drone
        self.leash = leash
        self.context = zmq.Context()
        self.sub_socket = self.context.socket(zmq.SUB)
        self.sub_socket.connect('tcp://localhost:5556')
        self.sub_socket.setsockopt(zmq.SUBSCRIBE, b'')
        self.image_res = (640, 480)
        self.pixel_center = (self.image_res[0] / 2, self.image_res[1] / 2)
        self.HFOV = 69
        self.VFOV = 43
        super().__init__()

    def find_intersection(self, target_dir, target_insct):
        plane_pt = np.array([0, 0, 0])
        plane_norm = np.array([0, 0, 1])

        if plane_norm.dot(target_dir).all() == 0:
            return None

        t = (plane_norm.dor(plane_pt) - plane)norm.dot(target_insct)) / plane_norm.dot(target_dir)
        return target_insct + (t * target_dir)
    
    def get_movement_vectors(self, yaw, pitch):
        gatt = drone.get_state(attitude)
        current_gimbal_pitch = gatt[0]["pitch_absolute"]
        alt = drone.get_state(AltitudeChanged)
        current_drone_altitude = att["altitude"]
        
        forward_vec = [0, 1, 0]
        r = R.from_euler('ZYX', [yaw, 0, pitch + current_gimbal_pitch], degrees=True)
        target_dir = r.as_matrix().dot(forward_vec)
        target_vec = self.find_intersection(target_dir, np.array([0, 0, alt]))
        
        leash_vec = self.leash * (target_vec / np.linalg.norm(target_vec))
        movement_vec = leash_vec - target_vec

        return movement_vec[0], movement_vec[1]

    def calculate_offsets(self, box):
        target_x_pix = int((((box[3] - box[1]) / 2.0) + box[1]) * self.image_res[0])
        target_y_pix = int((1 - (((box[2] - box[0]) / 2.0) + box[0])) * self.image_res[1])
        target_yaw_angle = ((target_x_pix - self.pixel_center[0]) / self.pixel_center[0]) * (self.HFOV / 2)
        target_pitch_angle = ((target_y_pix - self.pixel_center[1]) / self.pixel_center[1]) * (self.VFOV / 2)

        drone_roll, drone_pitch = self.get_movement_vectors(target_yaw_angle, target_pitch_angle)

        print(f"PITCH: {target_pitch_angle}, YAW: {target_yaw_angle}, SPEED: {speed}")
        return target_pitch_angle, target_yaw_angle, drone_pitch, drone_roll

    def clamp(self, value, minimum, maximum):
        return max(minimum, min(new_index, maximum))

    def gain(self, gpitch, dyaw, dpitch, droll):
        dyaw = self.clamp(int(dyaw * 2), -100, 100)
        dpitch = self.clamp(int(dpitch * 3), -100, 100)
        droll = self.clamp(int(droll * 3), -100, 100)
        gpitch = gpitch

        return gpitch, dyaw, dpitch, droll

    def execute_PCMD(self, gpitch, dyaw, dpitch, droll):
        gpitch, dyaw, dpitch, droll = self.gain(gpitch, dyaw, dpitch, droll)
        self.drone(PCMD(1, droll, dpitch, dyaw, 0, timestampAndSeqNum=0))
        gatt = drone.get_state(attitude)
        current_gimbal_pitch = gatt[0]["pitch_absolute"]
        self.drone(set_target(0, control_mode.position, "none", 0.0, "absolute", current_gimbal_pitch + gpitch, "none", 0.0))

    def run(self):
        self.tracking = False
        self.active = True

        while self.active:
            try:
                det = json.loads(self.sub_socket.recv_json())
                if len(det) > 0:
                    if not self.tracking:
                        print("Starting new track on object: \"{0}\"".format(det[0]["class"]))
                    else:
                        print(f"Got detection from the cloudlet: {det}")
                    self.tracking = True
                    gimbal_pitch, drone_yaw, drone_pitch, drone_roll  = self.calculate_offsets(det[0]["box"])
                    self.execute_PCMD(gimbal_pitch, drone_yaw, drone_pitch, drone_roll)
            except Exception as e:
                print(f"Exception: {e}")
            time.sleep(0.05)

    def stop(self):
        self.active = False
        self.tracking = False
