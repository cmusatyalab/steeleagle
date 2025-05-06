# OpenScout
#   - Distributed Automated Situational Awareness
#
#   Author: Thomas Eiszler <teiszler@andrew.cmu.edu>
#
#   Copyright (C) 2020 Carnegie Mellon University
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
#

import time
import os
import cv2
import numpy as np
import logging
from gabriel_server import cognitive_engine
from gabriel_protocol import gabriel_pb2
import protocol.common_pb2 as common
import protocol.controlplane_pb2 as control_plane
import protocol.gabriel_extras_pb2 as gabriel_extras
from PIL import Image, ImageDraw
import traceback
import json
from scipy.spatial.transform import Rotation as R
import redis
import torch

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class PytorchPredictor():
    def __init__(self, model, threshold):
        path_prefix = './model/'
        model_path = path_prefix + model + '.pt'
        logger.info(f"Loading new model {model} at {model_path}...")
        self.detection_model = self.load_model(model_path)
        self.detection_model.conf = threshold
        self.output_dict = None

    def load_model(self, model_path):
        # Load model
        model = torch.hub.load('ultralytics/yolov5', 'custom', path=model_path)
        return model

    def infer(self, image):
        return self.model(image)

class OpenScoutObjectEngine(cognitive_engine.Engine):
    ENGINE_NAME = "openscout-object"

    def __init__(self, args):
        self.detector = PytorchPredictor(args.model, args.threshold)
        self.threshold = args.threshold
        self.store_detections = args.store
        self.model = args.model
        self.drone_type = args.drone
        self.r = redis.Redis(host='redis', port=args.redis, username='steeleagle', password=f'{args.auth}',decode_responses=True)
        self.r.ping()
        logger.info(f"Connected to redis on port {args.redis}...")
        #timing vars
        self.count = 0
        self.lasttime = time.time()
        self.lastcount = 0
        self.lastprint = self.lasttime
        self.hsv_threshold = args.hsv_threshold
        self.search_radius = args.radius
        self.ttl_secs = 1200

        if args.exclude:
            self.exclusions = list(map(int, args.exclude.split(","))) #split string to int list
            logger.info("Excluding the following class ids: {}".format(self.exclusions))
        else:
            self.exclusions = None

        logger.info("Predictor initialized with the following model path: {}".format(args.model))
        logger.info("Confidence Threshold: {}".format(self.threshold))

        if self.store_detections:
            self.watermark = Image.open(os.getcwd()+"/watermark.png")
            self.storage_path = os.getcwd()+"/images/"
            try:
                os.makedirs(self.storage_path+"/detected")
            except FileExistsError:
                logger.info("Images directory already exists.")
            logger.info("Storing detection images at {}".format(self.storage_path))

        logger.info(f"Search radius when considering duplicate detections: {self.search_radius}")

    def find_intersection(self, target_dir, target_insct):
        plane_pt = np.array([0, 0, 0])
        plane_norm = np.array([0, 0, 1])

        if (plane_norm.dot(target_dir).all() == 0):
            return None

        t = (plane_norm.dot(plane_pt) - plane_norm.dot(target_insct)) / plane_norm.dot(target_dir)
        return target_insct + (t * target_dir)

    def estimateGPS(self, drone_lat, drone_lon, camera_pitch, drone_yaw, drone_elev, target_x_pix, target_y_pix):
        # Establish parameters.
        EARTH_RADIUS = 6378137.0
        north_vec = np.array([0, 1, 0]) # Create a vector pointing due north.
        if self.drone_type == 'anafi':
            HFOV = 69 # Horizontal FOV An.
            VFOV = 43 # Vertical FOV.
        elif self.drone_type ==  'usa':
            HFOV = 69 # Horizontal FOV An.
            VFOV = 43 # Vertical FOV.
        else:
            raise "Unsupported drone type!"
        pixel_center = (1280/2, 720/2) # Center pixel location of the camera.

        # Perform rotations.
        logger.info("Pitch: {0}, Yaw: {1}, Elev: {2}".format(camera_pitch, drone_yaw, drone_elev))

        r = R.from_euler('ZYX', [drone_yaw, 0, camera_pitch], degrees=True) # Rotate the due north vector to camera center.
        camera_center = r.as_matrix().dot(north_vec)

        logger.info("Camera centered at: ({0}, {1}, {2})".format(camera_center[0], camera_center[1], camera_center[2]))

        target_yaw_angle = ((target_x_pix - pixel_center[0]) / pixel_center[0]) * (HFOV / 2)
        target_pitch_angle = ((target_y_pix - pixel_center[1]) / pixel_center[1]) * (VFOV / 2)
        r = R.from_euler('ZYX', [drone_yaw + target_yaw_angle, 0, camera_pitch + target_pitch_angle], degrees=True) # Rotate the camera center vector to target center.
        target_dir = r.as_matrix().dot(north_vec)
        logger.info("Target yaw: {0}, Target pitch: {1}".format(target_yaw_angle, target_pitch_angle))
        logger.info("Target centered at: ({0}, {1}, {2})".format(target_dir[0], target_dir[1], target_dir[2]))

        # Finding the intersection with the plane.
        insct = self.find_intersection(target_dir, np.array([0, 0, drone_elev]))
        logger.info("Intersection with ground plane: ({0}, {1}, {2})".format(insct[0], insct[1], insct[2]))

        est_lat = drone_lat + (180 / np.pi) * (insct[1] / EARTH_RADIUS)
        est_lon = drone_lon + (180 / np.pi) * (insct[0] / EARTH_RADIUS) / np.cos(drone_lat)
        logger.info("Estimated GPS location: ({0}, {1})".format(est_lat, est_lon))
        return est_lat, est_lon

    def storeDetection(self, drone, lat, lon, cls, conf, link=""):
        object_name = f"{cls}-{os.urandom(2).hex()}"
        self.r.geoadd("detections", [lon, lat, object_name])

        object_key = f"objects:{object_name}"
        self.r.hset(object_key, "last_seen", f"{time.time()}")
        self.r.hset(object_key, "drone_id", f"{drone}")
        self.r.hset(object_key, "cls", f"{cls}")
        self.r.hset(object_key, "confidence", f"{conf}")
        self.r.hset(object_key, "link", f"{link}")
        self.r.hset(object_key, "longitude", f"{lon}")
        self.r.hset(object_key, "latitude", f"{lat}")
        self.r.expire(object_key, self.ttl_secs)
        logger.debug(f"Updating {object_key} status: last_seen: {time.time()}")

    def passes_hsv_filter(self, image, bbox, hsv_min=[30,100,100], hsv_max=[50,255,255], threshold=5.0,) -> bool:
        cropped = image[round(bbox[0]):round(bbox[2]), round(bbox[1]):round(bbox[3])]
        hsv = cv2.cvtColor(cropped, cv2.COLOR_RGB2HSV)
        lower_boundary = np.array(hsv_min)
        upper_boundary = np.array(hsv_max)
        mask = cv2.inRange(hsv, lower_boundary, upper_boundary)
        cv2.bitwise_and(cropped, cropped, mask=mask)
        percent = round(np.count_nonzero(mask) / np.size(mask) * 100, 2)
        logger.debug(f"HSV Filter Result: lower_bound:{hsv_min}, upper_bound:{hsv_max}, mask percentage:{percent}%")
        return (percent >= threshold)

    def load_model(self, model_name):
        path = './model/'+ model_name + '.pt'
        if not os.path.exists(path):
            logger.error(f"Model {path} not found. Sticking with previous model.")
        else:
            self.detector = PytorchPredictor(model_name, self.threshold)
            self.model = model_name

    def handle(self, input_frame):
        if input_frame.payload_type == gabriel_pb2.PayloadType.TEXT:
            #if the payload is TEXT, say from a CNC client, we ignore
            status = gabriel_pb2.ResultWrapper.Status.WRONG_INPUT_FORMAT
            result_wrapper = cognitive_engine.create_result_wrapper(status)
            result_wrapper.result_producer_name.value = self.ENGINE_NAME
            result = gabriel_pb2.ResultWrapper.Result()
            result.payload_type = gabriel_pb2.PayloadType.TEXT
            result.payload = 'Ignoring TEXT payload.'.encode(encoding="utf-8")
            result_wrapper.results.append(result)
            return result_wrapper

        extras = cognitive_engine.unpack_extras(gabriel_extras.Extras, input_frame)

        if not extras.cpt_request.HasField('cpt'):
            logger.error("Compute configuration not found")
            status = gabriel_pb2.ResultWrapper.Status.UNSPECIFIED_ERROR
            result_wrapper = cognitive_engine.create_result_wrapper(status)
            result_wrapper.result_producer_name.value = self.ENGINE_NAME
            result = gabriel_pb2.ResultWrapper.Result()
            result.payload_type = gabriel_pb2.PayloadType.TEXT
            result.payload = 'Expected compute configuration to be specified'.encode(encoding="utf-8")
            result_wrapper.results.append(result)
            return result_wrapper

        cpt_config = extras.cpt_request.cpt

        if cpt_config.model != '' and cpt_config.model != self.model:
            self.load_model(cpt_config.model)

        self.t0 = time.time()
        results, image_np = self.process_image(input_frame.payloads[0])
        status = gabriel_pb2.ResultWrapper.Status.SUCCESS
        result_wrapper = cognitive_engine.create_result_wrapper(status)
        result_wrapper.result_producer_name.value = self.ENGINE_NAME

        if len(results.pred) > 0:
            result = self.process_results(image_np, results, cpt_config, extras.telemetry, extras.telemetry.drone_name)
            if result is not None:
                result_wrapper.results.append(result)

        response = control_plane.Response()
        response.seq_num = extras.cpt_request.seq_num
        response.timestamp.GetCurrentTime()
        response.resp = common.ResponseStatus.OK
        result_wrapper.extras.Pack(response)

        self.count += 1

        if self.t1 - self.lastprint > 5:
            self.print_inference_stats()

        self.lasttime = self.t1

        return result_wrapper

    def process_results(self, image_np, results, cpt_config, telemetry, drone_id):
        df = results.pandas().xyxy[0] # pandas dataframe
        #convert dataframe to python lists
        classes = df['class'].values.tolist()
        scores = df['confidence'].values.tolist()
        names = df['name'].values.tolist()

        result = gabriel_pb2.ResultWrapper.Result()
        result.payload_type = gabriel_pb2.PayloadType.TEXT

        detections_above_threshold = False
        r = []
        timestamp_millis = int(time.time() * 1000)
        filename = str(timestamp_millis) + ".jpg"
        for i in range(0, len(classes)):
            if self.exclusions is not None and classes[i] in self.exclusions:
                continue
            if scores[i] > self.threshold:
                detections_above_threshold = True
                logger.info("Detected : {} - Score: {:.3f}".format(names[i],scores[i]))

                box = [df['ymin'][i], df['xmin'][i], df['ymax'][i], df['xmax'][i]]

                target_x_pix = int(((box[3] - box[1]) / 2.0) + box[1]) * image_np.shape[1]
                target_y_pix = int(((box[2] - box[0]) / 2.0) + box[0]) * image_np.shape[0]

                position = telemetry.global_position
                gimbal_pitch = telemetry.gimbal_pose.pitch

                # position.heading is sent in degrees
                lat, lon = self.estimateGPS(position.latitude, position.longitude, gimbal_pitch, position.heading, position.absolute_altitude, target_x_pix, target_y_pix)

                hsv_filter = False
                if cpt_config.HasField('lower_bound'):
                    lower_bound = [cpt_config.lower_bound.H, cpt_config.lower_bound.S, cpt_config.lower_bound.V]
                    upper_bound = [cpt_config.upper_bound.H, cpt_config.upper_bound.S, cpt_config.upper_bound.V]
                    hsv_filter = self.passes_hsv_filter(image_np, box, lower_bound, upper_bound, threshold=self.hsv_threshold)
                # first do a geosearch to see if there is a match within radius
                objects = self.r.geosearch(
                    "detections",
                    longitude=np.clip(lon, -180, 180),
                    latitude=np.clip(lat, -90, 90),
                    radius=self.search_radius,
                    unit="m",
                )

                if len(objects) == 0:
                    r.append({
                        "id": i,
                        "class": names[i],
                        "score": scores[i],
                        "lat": lat, "lon":
                        lon, "box": box,
                        "hsv_filter": hsv_filter
                    })
                    self.storeDetection(drone_id, lat, lon, names[i],scores[i], os.environ["WEBSERVER"]+"/detected/"+filename if self.store_detections else "" )
                else:
                    for obj in objects:
                        id = self.r.hget(obj, "drone_id")
                        if id == drone_id:
                            r.append({
                                "id": i,
                                "class": names[i],
                                "score": scores[i],
                                "lat": lat, "lon":
                                lon, "box": box,
                                "hsv_filter": hsv_filter
                            })
                            self.storeDetection(drone_id, lat, lon, names[i],scores[i], os.environ["WEBSERVER"]+"/detected/"+filename if self.store_detections else "" )

        if not detections_above_threshold:
            return None

        logger.info(json.dumps(r,sort_keys=True, indent=4))
        result.payload = json.dumps(r).encode(encoding="utf-8")

        if not self.store_detections:
            return result

        try:
            #results._run(save=True, labels=True, save_dir=Path("openscout-vol/"))
            results.render()
            img = Image.fromarray(results.ims[0])
            draw = ImageDraw.Draw(img)
            draw.bitmap((0,0), self.watermark, fill=None)

            path = self.storage_path + "/detected/" + filename
            img.save(path, format="JPEG")

            path = self.storage_path + "/detected/latest.jpg"
            img.save(path, format="JPEG")

            logger.info("Stored image: {}".format(path))
            if cpt_config.HasField('lower_bound'):
                img = self.run_hsv_filter(image_np, cpt_config)
                path = self.storage_path + "/detected/hsv.jpg"
                img.save(path, format="JPEG")
        except IndexError:
            logger.error(f"IndexError while getting bounding boxes [{traceback.format_exc()}]")

        return result

    def run_hsv_filter(self, image_np, cpt_config):
        hsv = cv2.cvtColor(image_np, cv2.COLOR_RGB2HSV)
        lower_boundary = np.array([cpt_config.lower_bound.H, cpt_config.lower_bound.S, cpt_config.lower_bound.V])
        upper_boundary = np.array([cpt_config.upper_bound.H, cpt_config.upper_bound.S, cpt_config.upper_bound.V])
        mask = cv2.inRange(hsv, lower_boundary, upper_boundary)
        final = cv2.bitwise_and(hsv, hsv, mask=mask)
        final = cv2.cvtColor(final, cv2.COLOR_HSV2RGB)
        return Image.fromarray(final)

    def process_image(self, image):
        self.t0 = time.time()
        np_data = np.fromstring(image, dtype=np.uint8)
        img = cv2.imdecode(np_data, cv2.IMREAD_COLOR)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        output_dict = self.inference(img)
        self.t1 = time.time()
        return output_dict, img

    def print_inference_stats(self):
        logger.info("inference time {0:.1f} ms, ".format((self.t1 - self.t0) * 1000))
        logger.info("wait {0:.1f} ms, ".format((self.t0 - self.lasttime) * 1000))
        logger.info("fps {0:.2f}".format(1.0 / (self.t1 - self.lasttime)))
        logger.info(
            "avg fps: {0:.2f}".format(
                (self.count - self.lastcount) / (self.t1 - self.lastprint)
            )
        )
        self.lastcount = self.count
        self.lastprint = self.t1

    def inference(self, img):
        """Allow timing engine to override this"""
        return self.detector.detection_model(img)

