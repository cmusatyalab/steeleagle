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

import json
import logging
import os
import time
import traceback

import cv2
import numpy as np
import redis
from gabriel_protocol import gabriel_pb2
from gabriel_server import cognitive_engine
from PIL import Image
from pygeodesy.sphericalNvector import LatLon
from pykml import parser
from scipy.spatial.transform import Rotation as R
from ultralytics import YOLO

import protocol.common_pb2 as common
import protocol.controlplane_pb2 as control_plane
import protocol.gabriel_extras_pb2 as gabriel_extras

logger = logging.getLogger(__name__)


class PytorchPredictor:
    def __init__(self, model, threshold):
        path_prefix = "./model/"
        model_path = path_prefix + model + ".pt"
        logger.info(f"Loading new model {model} at {model_path}...")
        self.detection_model = self.load_model(model_path)
        self.detection_model.conf = threshold
        self.output_dict = None

    def load_model(self, model_path):
        # Load model
        model = YOLO(model_path)
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
        self.r = redis.Redis(
            host="redis",
            port=args.redis,
            username="steeleagle",
            password=f"{args.auth}",
            decode_responses=True,
        )
        self.r.ping()
        logger.info(f"Connected to redis on port {args.redis}...")
        # timing vars
        self.count = 0
        self.lasttime = time.time()
        self.lastcount = 0
        self.lastprint = self.lasttime
        self.hsv_threshold = args.hsv_threshold
        self.search_radius = args.radius
        self.ttl_secs = args.ttl
        self.geofence = []
        self.geofence_enabled = args.geofence_enabled
        self.last_geodb_gc_time = time.time()

        fence_path = os.getcwd() + "/geofence/" + args.geofence
        if not os.path.exists(fence_path) or not os.path.isfile(fence_path):
            logger.error(f"Geofence KML file not found or is not a file: {fence_path}")
        else:
            # build geofence from coordinates inside Polygon element of KML file
            with open(f"{fence_path}", encoding="utf-8") as f:
                root = parser.parse(f).getroot()
                coords = root.Document.Placemark.Polygon.outerBoundaryIs.LinearRing.coordinates.text
                for c in coords.split():
                    lon, lat, alt = c.split(",")
                    p = LatLon(lat, lon)
                    self.geofence.append(p)

            logger.info(f"GeoFence read: {self.geofence}")

        if args.exclude:
            self.exclusions = list(
                map(int, args.exclude.split(","))
            )  # split string to int list
            logger.info(f"Excluding the following class ids: {self.exclusions}")
        else:
            self.exclusions = None

        logger.info(
            f"Predictor initialized with the following model path: {args.model}"
        )
        logger.info(f"Confidence Threshold: {self.threshold}")

        if self.store_detections:
            self.watermark = Image.open(os.getcwd() + "/watermark.png")
            self.storage_path = os.getcwd() + "/images/"
            try:
                os.makedirs(self.storage_path + "/detected")
            except FileExistsError:
                logger.info("Images directory already exists.")
            logger.info(f"Storing detection images at {self.storage_path}")

            self.drone_storage_path = os.path.join(
                self.storage_path, "detected", "drones"
            )
            self.class_storage_path = os.path.join(
                self.storage_path, "detected", "classes"
            )
            try:
                os.makedirs(self.drone_storage_path)
                os.makedirs(self.class_storage_path)
            except FileExistsError:
                pass

        logger.info(
            f"Search radius when considering duplicate detections: {self.search_radius}"
        )

    def find_intersection(self, target_dir, target_insct):
        plane_pt = np.array([0, 0, 0])
        plane_norm = np.array([0, 0, 1])

        if plane_norm.dot(target_dir).all() == 0:
            return None

        t = (plane_norm.dot(plane_pt) - plane_norm.dot(target_insct)) / plane_norm.dot(
            target_dir
        )
        return target_insct + (t * target_dir)

    def calculate_target_pitch_yaw(self, box, image_np, telemetry):
        img_width = image_np.shape[1]
        img_height = image_np.shape[0]
        pixel_center = (img_width / 2, img_height / 2)
        logger.info(
            f"Image Width: {img_width}px, Image Height: {img_height}px, Center {pixel_center}"
        )
        # eventually these should come from something like a drone .cap file
        HFOV = 69  # Horizontal FOV An.
        VFOV = 43  # Vertical FOV.

        target_x_pix = img_width - int(((box[3] - box[1]) / 2.0) + box[1])
        target_y_pix = img_height - int(
            box[0]
        )  # int(((box[2] - box[0]) / 2.0) + box[0])
        target_yaw_angle = ((target_x_pix - pixel_center[0]) / pixel_center[0]) * (
            HFOV / 2
        )
        target_pitch_angle = ((target_y_pix - pixel_center[1]) / pixel_center[1]) * (
            VFOV / 2
        )
        target_bottom_pitch_angle = (
            ((img_height - box[2]) - pixel_center[1]) / pixel_center[1]
        ) * (VFOV / 2)

        gimbal_pitch = telemetry.gimbal_pose.pitch
        logger.info(
            f"Gimbal Pitch: {gimbal_pitch} + Bottom Angle {target_bottom_pitch_angle})"
        )
        object_heading = telemetry.global_position.heading + target_yaw_angle
        logger.info(
            f"Heading: {telemetry.global_position.heading} + Target Yaw Offset {target_yaw_angle})"
        )
        return (
            gimbal_pitch + target_bottom_pitch_angle,
            object_heading
            % 360,  # % 360 to adjust for the cases when we wrap around 0 degrees due to the target_yaw_angle
        )

    def estimate_gps(self, lat, lon, pitch, yaw, alt):
        EARTH_RADIUS = 6378137.0
        vf = [0, 1, 0]
        r = R.from_euler("ZYX", [yaw, 0, pitch], degrees=True)
        target_dir = r.as_matrix().dot(vf)
        target_vec = self.find_intersection(target_dir, np.array([0, 0, alt]))

        logger.info(
            f"Intersection with ground plane: ({target_vec[0]}, {target_vec[1]}, {target_vec[2]})"
        )

        est_lat = lat + (180 / np.pi) * (target_vec[1] / EARTH_RADIUS)
        est_lon = lon + (180 / np.pi) * (target_vec[0] / EARTH_RADIUS) / np.cos(lat)
        logger.info(f"Estimated GPS location: ({est_lat}, {est_lon})")
        return est_lat, est_lon

    def geodb_garbage_collection(self):
        logger.info("Performing geospatial database garbage collection")
        objects = {}
        for item in self.r.zscan_iter("detections"):
            key = item[0]
            score = item[1]
            if self.r.exists(f"objects:{key}"):
                objects[key] = score

        self.r.delete("detections")
        if not objects:
            return
        self.r.zadd("detections", objects)

    def store_detection_db(self, drone, lat, lon, cls, conf, link="", object_name=None):
        if object_name is None:
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

    def passes_hsv_filter(
        self,
        image,
        bbox,
        hsv_min=[30, 100, 100],
        hsv_max=[50, 255, 255],
        threshold=5.0,
    ) -> bool:
        cropped = image[
            round(bbox[0]) : round(bbox[2]), round(bbox[1]) : round(bbox[3])
        ]
        hsv = cv2.cvtColor(cropped, cv2.COLOR_RGB2HSV)
        lower_boundary = np.array(hsv_min)
        upper_boundary = np.array(hsv_max)
        mask = cv2.inRange(hsv, lower_boundary, upper_boundary)
        cv2.bitwise_and(cropped, cropped, mask=mask)
        percent = round(np.count_nonzero(mask) / np.size(mask) * 100, 2)
        logger.debug(
            f"HSV Filter Result: lower_bound:{hsv_min}, upper_bound:{hsv_max}, mask percentage:{percent}%"
        )
        return percent >= threshold

    def load_model(self, model_name):
        path = "./model/" + model_name + ".pt"
        if not os.path.exists(path):
            logger.error(f"Model {path} not found. Sticking with previous model.")
        else:
            self.detector = PytorchPredictor(model_name, self.threshold)
            self.model = model_name

    def handle(self, input_frame):
        if input_frame.payload_type == gabriel_pb2.PayloadType.TEXT:
            # if the payload is TEXT, say from a CNC client, we ignore
            status = gabriel_pb2.ResultWrapper.Status.WRONG_INPUT_FORMAT
            result_wrapper = cognitive_engine.create_result_wrapper(status)
            result_wrapper.result_producer_name.value = self.ENGINE_NAME
            result = gabriel_pb2.ResultWrapper.Result()
            result.payload_type = gabriel_pb2.PayloadType.TEXT
            result.payload = b"Ignoring TEXT payload."
            result_wrapper.results.append(result)
            return result_wrapper

        extras = cognitive_engine.unpack_extras(gabriel_extras.Extras, input_frame)

        if not extras.cpt_request.HasField("cpt"):
            logger.error("Compute configuration not found")
            status = gabriel_pb2.ResultWrapper.Status.UNSPECIFIED_ERROR
            result_wrapper = cognitive_engine.create_result_wrapper(status)
            result_wrapper.result_producer_name.value = self.ENGINE_NAME
            result = gabriel_pb2.ResultWrapper.Result()
            result.payload_type = gabriel_pb2.PayloadType.TEXT
            result.payload = b"Expected compute configuration to be specified"
            result_wrapper.results.append(result)
            return result_wrapper

        cpt_config = extras.cpt_request.cpt

        if cpt_config.model != "" and cpt_config.model != self.model:
            self.load_model(cpt_config.model)

        self.t0 = time.time()
        results, image_np = self.process_image(input_frame.payloads[0])
        status = gabriel_pb2.ResultWrapper.Status.SUCCESS
        result_wrapper = cognitive_engine.create_result_wrapper(status)
        result_wrapper.result_producer_name.value = self.ENGINE_NAME

        if len(results) > 0:
            gabriel_result = self.process_results(
                image_np,
                results,
                cpt_config,
                extras.telemetry,
                extras.telemetry.drone_name,
            )

            if gabriel_result is not None:
                result_wrapper.results.append(gabriel_result)

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
        df = results[0].to_df()  # pandas dataframe
        # convert dataframe to python lists
        if df.size > 0:
            classes = df["class"].values.tolist()
            scores = df["confidence"].values.tolist()
            names = df["name"].values.tolist()
        else:
            classes = []
            scores = []
            names = []

        gabriel_result = gabriel_pb2.ResultWrapper.Result()
        gabriel_result.payload_type = gabriel_pb2.PayloadType.TEXT

        detections_above_threshold = False
        detections = []
        timestamp_millis = int(time.time() * 1000)
        filename = str(timestamp_millis) + ".jpg"
        if self.store_detections:
            detection_url = os.path.join(
                os.environ["WEBSERVER"], "detected", "drones", drone_id, filename
            )
        else:
            detection_url = ""

        run_hsv_filter = cpt_config.HasField("lower_bound")

        for i in range(0, len(classes)):
            if self.exclusions is not None and classes[i] in self.exclusions:
                continue

            if scores[i] > self.threshold:
                detections_above_threshold = True
                logger.info(f"Detected : {names[i]} - Score: {scores[i]:.3f}")

                box = df["box"][i]
                box = [box["y1"], box["x1"], box["y2"], box["x2"]]
                target_pitch, target_yaw = self.calculate_target_pitch_yaw(
                    box, image_np, telemetry
                )

                # Estimate GPS coordinates of detected object
                position = telemetry.global_position
                lat, lon = self.estimate_gps(
                    position.latitude,
                    position.longitude,
                    target_pitch,
                    target_yaw,
                    telemetry.relative_position.up,
                )

                lon = np.clip(lon, -180, 180)
                lat = np.clip(lat, -85, 85)
                p = LatLon(lat, lon)

                hsv_filter_passed = False
                if run_hsv_filter:
                    lower_bound = cpt_config.lower_bound
                    upper_bound = cpt_config.upper_bound
                    lower_bound = [lower_bound.h, lower_bound.s, lower_bound.v]
                    upper_bound = [upper_bound.h, upper_bound.s, upper_bound.v]
                    hsv_filter_passed = self.passes_hsv_filter(
                        image_np,
                        box,
                        lower_bound,
                        upper_bound,
                        threshold=self.hsv_threshold,
                    )

                detection = {
                    "id": drone_id,
                    "class": names[i],
                    "score": scores[i],
                    "lat": lat,
                    "lon": lon,
                    "box": box,
                    "hsv_filter": hsv_filter_passed,
                }

                if not self.geofence_enabled:
                    detections.append(detection)
                    self.store_detection_db(
                        drone_id, lat, lon, names[i], scores[i], detection_url
                    )
                    continue

                # if there is no geofence, or the estimated object location is within the geofence...
                if len(self.geofence) == 0 or p.isenclosedBy(self.geofence):
                    passed, prev_obj = self.geofilter_passed(detection)
                    if passed:
                        detections.append(detection)
                        self.store_detection_db(
                            drone_id,
                            lat,
                            lon,
                            names[i],
                            scores[i],
                            detection_url,
                            prev_obj,
                        )

        if len(detections) == 0:
            return None

        logger.info(json.dumps(detections, sort_keys=True, indent=4))
        gabriel_result.payload = json.dumps(detections).encode(encoding="utf-8")

        if not self.store_detections:
            return gabriel_result if detections_above_threshold else None

        if run_hsv_filter:
            self.store_hsv_image(image_np, cpt_config, drone_id)

        # Store detection image
        if detections_above_threshold:
            try:
                im_bgr = results[0].plot()
                self.store_detections_disk(im_bgr, filename, drone_id, set(names))
            except IndexError:
                logger.error(
                    f"IndexError while getting bounding boxes [{traceback.format_exc()}]"
                )

        return gabriel_result if detections_above_threshold else None

    def store_detections_disk(self, im_bgr, filename, drone_id, uniq_classes):
        drone_dir = os.path.join(self.drone_storage_path, drone_id)

        if not os.path.exists(drone_dir):
            os.makedirs(drone_dir)

        # Save to drone dir
        drone_dir_path = os.path.join(drone_dir, filename)
        im_rgb = Image.fromarray(im_bgr[..., ::-1])  # RGB-order PIL image
        im_rgb.save(drone_dir_path)
        logger.debug(f"Stored image: {drone_dir_path}")

        path = os.path.join(drone_dir, "latest.jpg")
        im_rgb.save(path)
        logger.debug(f"Stored image: {path}")

        for cls in uniq_classes:
            # Save to class dir
            class_dir = os.path.join(self.class_storage_path, cls)
            if not os.path.exists(class_dir):
                os.makedirs(class_dir)
            path = os.path.join(class_dir, filename)
            logger.debug(f"Stored image: {path}")

            os.symlink(os.path.join("..", "..", "drones", drone_id, filename), path)

    def store_hsv_image(self, image_np, cpt_config, drone_id):
        img = self.run_hsv_filter(image_np, cpt_config)

        path = os.path.join(self.drone_storage_path, drone_id, "hsv.jpg")
        img.save(path, format="JPEG")

    def run_hsv_filter(self, image_np, cpt_config):
        hsv = cv2.cvtColor(image_np, cv2.COLOR_RGB2HSV)
        lower_boundary = np.array(
            [
                cpt_config.lower_bound.h,
                cpt_config.lower_bound.s,
                cpt_config.lower_bound.v,
            ]
        )
        upper_boundary = np.array(
            [
                cpt_config.upper_bound.h,
                cpt_config.upper_bound.s,
                cpt_config.upper_bound.v,
            ]
        )
        mask = cv2.inRange(hsv, lower_boundary, upper_boundary)
        final = cv2.bitwise_and(hsv, hsv, mask=mask)
        final = cv2.cvtColor(final, cv2.COLOR_HSV2RGB)
        return Image.fromarray(final)

    def process_image(self, image):
        self.t0 = time.time()
        np_data = np.fromstring(image, dtype=np.uint8)
        img = cv2.imdecode(np_data, cv2.IMREAD_COLOR)
        # img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        results = self.inference(img)
        self.t1 = time.time()
        return results, img

    def geofilter_passed(self, detection):
        cls = detection["class"]
        drone_id = detection["id"]

        now_secs = time.time()
        if now_secs - self.last_geodb_gc_time >= self.ttl_secs:
            self.geodb_garbage_collection()
            self.last_geodb_gc_time = now_secs

        # first do a geosearch to see if there is a match within radius
        objects = self.r.geosearch(
            "detections",
            longitude=detection["lon"],
            latitude=detection["lat"],
            radius=self.search_radius,
            unit="m",
        )
        if len(objects) == 0:
            logger.info(
                f"Adding detection for {cls} for drone {drone_id} for the first time"
            )
            return (True, None)

        logger.info(f"Objects already exist within search radius: {objects}")

        for obj in objects:
            d = self.r.hgetall(f"objects:{obj}")
            if d and d["cls"] == cls:
                if d["drone_id"] == drone_id:
                    logger.debug(
                        f"Drone {d['drone_id']} detected {obj} in same area, updating obj location"
                    )
                    return (True, obj)
                else:
                    logger.info(
                        f"Ignoring detection, {obj} already found by drone {d['drone_id']}"
                    )
                    return (False, None)
        return (True, None)

    def print_inference_stats(self):
        logger.info(f"inference time {(self.t1 - self.t0) * 1000:.1f} ms, ")
        logger.info(f"wait {(self.t0 - self.lasttime) * 1000:.1f} ms, ")
        logger.info(f"fps {1.0 / (self.t1 - self.lasttime):.2f}")
        logger.info(
            f"avg fps: {(self.count - self.lastcount) / (self.t1 - self.lastprint):.2f}"
        )
        self.lastcount = self.count
        self.lastprint = self.t1

    def inference(self, img):
        """Allow timing engine to override this"""
        return self.detector.detection_model.predict(
            img, conf=self.threshold, verbose=False
        )
