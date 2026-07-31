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

import argparse
import json
import logging
import os
import time
import traceback

import cv2
import numpy as np
import redis
import supervision as sv
from gabriel_protocol import gabriel_pb2
from gabriel_server import cognitive_engine, local_engine
from google.protobuf.any_pb2 import Any
from PIL import Image
from predictors import UnknownModelArchError, load_predictor
from pygeodesy.sphericalNvector import LatLon
from pykml import parser
from scipy.spatial.transform import Rotation as R
from steeleagle_protocol.v1 import common_pb2
from steeleagle_protocol.v1.messages.result import result_pb2
from steeleagle_protocol.v1.messages.telemetry import telemetry_pb2 as telemetry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(filename)s:%(lineno)d - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def annotate_detections(image_bgr, detections):
    labels = [
        f"{name} {confidence:.2f}"
        for name, confidence in zip(
            detections.data["class_name"], detections.confidence
        )
    ]
    annotated = sv.BoxAnnotator().annotate(image_bgr.copy(), detections)
    return sv.LabelAnnotator().annotate(annotated, detections, labels=labels)


class OpenScoutObjectEngine(cognitive_engine.Engine):
    ENGINE_NAME = "openscout-object"

    def __init__(self, args):
        self.detector = load_predictor(args.model, args.threshold)
        self.threshold = args.threshold
        self.store_detections = args.store
        self.model = args.model
        self.unittest = args.unittest
        if not self.unittest:
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

            self.vehicle_storage_path = os.path.join(
                self.storage_path, "detected", "vehicles"
            )
            self.class_storage_path = os.path.join(
                self.storage_path, "detected", "classes"
            )
            try:
                os.makedirs(self.vehicle_storage_path)
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

    def calculate_target_pitch_yaw(self, box, image_np, position_info, gimbal_status):
        img_width = image_np.shape[1]
        img_height = image_np.shape[0]
        pixel_center = (img_width / 2, img_height / 2)
        logger.info(
            f"Image Width: {img_width}px, Image Height: {img_height}px, Center {pixel_center}"
        )
        # TODO: eventually these should come from something like a vehicle .cap file
        HFOV = 69  # Horizontal FOV An.
        VFOV = 43  # Vertical FOV.

        # Change frame of reference from top-left of image to center of image
        target_x_pix = int(((box[3] - box[1]) / 2) + box[1]) - (img_width / 2)
        target_y_pix = (img_height / 2) - int(box[2])

        target_yaw_angle = (target_x_pix / img_width) * HFOV
        target_bottom_pitch_angle = (target_y_pix / img_height) * VFOV

        gimbal_pitch = gimbal_status.pose_body.pitch
        object_heading = position_info.global_position.heading + target_yaw_angle
        logger.info(
            f"BBox: {box}\nTargetXPix: {target_x_pix}\nTargetYPix: {target_y_pix}\nGimbal Pitch: {gimbal_pitch}\nBottom Angle {target_bottom_pitch_angle}\nHeading: {position_info.global_position.heading}\nTarget Yaw Offset {target_yaw_angle}\n"
        )
        return (
            gimbal_pitch + target_bottom_pitch_angle,
            object_heading
            % 360,  # % 360 to adjust for the cases when we wrap around 0 degrees due to the target_yaw_angle
        )

    def estimate_gps(self, lat_deg, lon_deg, pitch_deg, yaw_deg, altitude):
        EARTH_RADIUS = 6378137.0

        vf = np.array([0, 1, 0])
        r = R.from_euler("ZYX", [yaw_deg, 0, pitch_deg], degrees=True)
        target_dir = r.as_matrix().dot(vf)

        drone_pos = np.array([0, 0, altitude])
        target_vec = self.find_intersection(target_dir, drone_pos)

        if target_vec is None:
            logger.warning("Could not find intersection with ground plane")
            return lat_deg, lon_deg

        logger.info(
            f"Intersection with ground plane: ({target_vec[0]}, {target_vec[1]}, {target_vec[2]})"
        )

        north_offset = target_vec[1]
        east_offset = target_vec[0]

        lat_rad = np.deg2rad(lat_deg)
        lat_offset = north_offset / EARTH_RADIUS
        lon_offset = east_offset / (EARTH_RADIUS * np.cos(lat_rad))

        est_lat = lat_deg + np.rad2deg(lat_offset)
        est_lon = lon_deg + np.rad2deg(lon_offset)

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

    def store_latest_drone_detection_db(self, detections):
        vehicle_name = detections[0]["id"]
        key = f"latest-detection:{vehicle_name}"

        pipe = self.r.pipeline()
        pipe.delete(key)
        pipe.rpush(key, *[json.dumps(d) for d in detections])
        pipe.pexpire(key, 100)

        pipe.execute()

    def store_detection_db(self, detection, link="", object_name=None):
        if object_name is None:
            object_name = f"{detection['class']}-{os.urandom(2).hex()}"
        lon = detection["lon"]
        lat = detection["lat"]
        logger.info(f"Adding detection {lon=} {lat=} {object_name=}")
        self.r.geoadd("detections", [lon, lat, object_name])

        object_key = f"objects:{object_name}"
        y1, x1, y2, x2 = detection["box"]

        self.r.hset(
            object_key,
            mapping={
                "last_seen": time.time(),
                "id": detection["id"],
                "cls": detection["class"],
                "confidence": detection["score"],
                "link": link,
                "longitude": lon,
                "latitude": lat,
                "x_min": x1,
                "y_min": y1,
                "x_max": x2,
                "y_max": y2,
            },
        )
        self.r.expire(object_key, self.ttl_secs)
        logger.debug(f"Updating {object_key} status: last_seen: {time.time()}")

    def passes_hsv_filter(
        self,
        image,
        bbox,
        hsv_min=(30, 100, 100),
        hsv_max=(50, 255, 255),
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
        try:
            detector = load_predictor(model_name, self.threshold)
        except (FileNotFoundError, UnknownModelArchError) as e:
            logger.error(
                f"Failed to load model {model_name}: {e}. Sticking with previous model."
            )
            return
        self.detector = detector
        self.model = model_name

    def handle(self, input_frame, client_info):
        if input_frame.payload_type == gabriel_pb2.PayloadType.TEXT:
            # if the payload is TEXT, say from a CNC client, we ignore
            status = gabriel_pb2.Status()
            status.code = gabriel_pb2.StatusCode.WRONG_INPUT_FORMAT
            status.message = "Ignoring text payload"
            return cognitive_engine.Result(status, None)

        vehicle_info = common_pb2.VehicleInfo()
        client_info.Unpack(vehicle_info)
        vehicle_id = vehicle_info.vehicle_id

        frame = telemetry.EncodedFrame()
        assert input_frame.WhichOneof("payload") == "any_payload"
        assert input_frame.any_payload.Is(telemetry.EncodedFrame.DESCRIPTOR)
        input_frame.any_payload.Unpack(frame)

        self.t0 = time.time()

        gimbal_status = frame.gimbal_status if frame.HasField("gimbal_status") else None
        results, image_np = self.process_image(frame.encoded_data)
        detections = self.process_results(
            image_np,
            results,
            vehicle_id,
            frame.position_info,
            gimbal_status,
        )

        compute_result = result_pb2.ComputeResult()
        compute_result.timestamp.GetCurrentTime()

        try:
            if detections is not None:
                detection_result = result_pb2.DetectionResult()
                for d in detections:
                    det_object = result_pb2.Detection()
                    det_object.class_name = d["class"]
                    det_object.score = d["score"] * 100
                    bbox = result_pb2.BoundingBox(
                        x_min=float(np.clip(d["box"][1], 0.0001, 1.0)),
                        y_min=float(np.clip(d["box"][0], 0.0001, 1.0)),
                        x_max=float(np.clip(d["box"][3], 0.0001, 1.0)),
                        y_max=float(np.clip(d["box"][2], 0.0001, 1.0)),
                    )
                    det_object.bbox.CopyFrom(bbox)
                    detection_result.detections.append(det_object)
                compute_result.detection_result.CopyFrom(detection_result)

            any_payload = Any()
            any_payload.Pack(compute_result)
        except Exception as e:
            logger.error(e)

        self.count += 1

        if self.t1 - self.lastprint > 5:
            self.print_inference_stats()

        self.lasttime = self.t1

        status = gabriel_pb2.Status()
        return cognitive_engine.Result(status, any_payload)

    def process_results(
        self, image_np, sv_detections, vehicle_id, position_info, gimbal_status
    ):
        exclusions = self.exclusions or []
        sv_detections = sv_detections[~np.isin(sv_detections.class_id, exclusions)]

        detections = []
        timestamp_millis = int(time.time() * 1000)
        filename = str(timestamp_millis) + ".jpg"
        if self.store_detections:
            detection_url = os.path.join(
                os.environ["WEBSERVER"],
                "detected",
                "vehicles",
                vehicle_id,
                filename,
            )
        else:
            detection_url = ""

        run_hsv_filter = False
        img_height, img_width = image_np.shape[:2]

        for xyxy, confidence, class_name in zip(
            sv_detections.xyxy,
            sv_detections.confidence,
            sv_detections.data["class_name"],
        ):
            x1, y1, x2, y2 = xyxy
            logger.info(f"Detected : {class_name} - Score: {confidence:.3f}")
            box = [
                float(y1 / img_height),
                float(x1 / img_width),
                float(y2 / img_height),
                float(x2 / img_width),
            ]
            global_pos = position_info.global_position
            if gimbal_status is None:
                logger.warning(
                    "No gimbal attached to this frame, using the vehicle global location for target coordinates"
                )
                lon = global_pos.longitude
                lat = global_pos.latitude
                p = LatLon(lat, lon)
            else:
                target_pitch, target_yaw = self.calculate_target_pitch_yaw(
                    box, image_np, position_info, gimbal_status
                )

                rel_pos = position_info.relative_position
                lat, lon = self.estimate_gps(
                    global_pos.latitude,
                    global_pos.longitude,
                    target_pitch,
                    target_yaw,
                    rel_pos.z,
                )

                lon = float(np.clip(lon, -180, 180))
                lat = float(np.clip(lat, -85, 85))
                p = LatLon(lat, lon)

            hsv_filter_passed = False
            if run_hsv_filter:
                logger.info("TODO: need to get hsv bounds")
                # lower_bound = cpt_config.lower_bound
                # upper_bound = cpt_config.upper_bound
                # lower_bound = [lower_bound.h, lower_bound.s, lower_bound.v]
                # upper_bound = [upper_bound.h, upper_bound.s, upper_bound.v]
                # hsv_filter_passed = self.passes_hsv_filter(
                #     image_np,
                #     box,
                #     lower_bound,
                #     upper_bound,
                #     threshold=self.hsv_threshold,
                # )

            detection = {
                "id": vehicle_id,
                "class": class_name,
                "score": float(confidence),
                "lat": lat,
                "lon": lon,
                "box": box,
                "hsv_filter": hsv_filter_passed,
            }

            # Ignore this detection if geofence is enabled and this detection
            # is not within the geofence
            if (
                self.geofence_enabled
                and len(self.geofence) != 0
                and not p.isenclosedBy(self.geofence)
            ):
                continue

            passed, prev_obj = self.geofilter_passed(detection)
            if not passed:
                continue

            detections.append(detection)

            if self.unittest:
                continue
            self.store_detection_db(
                detection,
                detection_url,
                prev_obj,
            )

        if len(detections) == 0:
            return None

        logger.info(json.dumps(detections, sort_keys=True, indent=4))
        self.store_latest_drone_detection_db(detections)

        if run_hsv_filter and not self.unittest:
            logger.info("TODO: need to get hsv bounds")
            # self.store_hsv_image(image_np, cpt_config, vehicle_id)

        # Store detection image
        if self.store_detections and len(sv_detections) > 0 and not self.unittest:
            try:
                annotated = annotate_detections(image_np, sv_detections)
                self.store_detections_disk(
                    annotated,
                    filename,
                    vehicle_id,
                    sorted(set(sv_detections.data["class_name"].tolist())),
                )
            except IndexError:
                logger.error(
                    f"IndexError while getting bounding boxes [{traceback.format_exc()}]"
                )

        now_secs = time.time()
        if now_secs - self.last_geodb_gc_time >= self.ttl_secs:
            self.geodb_garbage_collection()
            self.last_geodb_gc_time = now_secs

        return detections

    def store_detections_disk(self, im_bgr, filename, vehicle_id, uniq_classes):
        vehicle_dir = os.path.join(self.vehicle_storage_path, vehicle_id)

        if not os.path.exists(vehicle_dir):
            os.makedirs(vehicle_dir)

        # Save to vehicle dir
        vehicle_dir_path = os.path.join(vehicle_dir, filename)
        im_rgb = Image.fromarray(im_bgr[..., ::-1])  # RGB-order PIL image
        im_rgb.save(vehicle_dir_path)
        logger.debug(f"Stored image: {vehicle_dir_path}")

        path = os.path.join(vehicle_dir, "latest.jpg")
        im_rgb.save(path)
        logger.debug(f"Stored image: {path}")

        for cls in uniq_classes:
            # Save to class dir
            class_dir = os.path.join(self.class_storage_path, cls)
            if not os.path.exists(class_dir):
                os.makedirs(class_dir)
            path = os.path.join(class_dir, filename)
            logger.debug(f"Stored image: {path}")

            os.symlink(os.path.join("..", "..", "vehicles", vehicle_id, filename), path)

    def store_hsv_image(self, image_np, cpt_config, vehicle_id):
        img = self.run_hsv_filter(image_np, cpt_config)

        path = os.path.join(self.vehicle_storage_path, vehicle_id, "hsv.jpg")
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
        np_data = np.frombuffer(image, dtype=np.uint8)
        img = cv2.imdecode(np_data, cv2.IMREAD_COLOR)
        # img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        results = self.inference(img)
        self.t1 = time.time()
        return results, img

    def geofilter_passed(self, detection):
        cls = detection["class"]
        vehicle_id = detection["id"]

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
                f"Adding detection for {cls} for vehicle {vehicle_id} for the first time"
            )
            return (True, None)

        logger.info(f"Objects already exist within search radius: {objects}")

        for obj in objects:
            d = self.r.hgetall(f"objects:{obj}")
            if d and d["cls"] == cls:
                if d["id"] == vehicle_id:
                    logger.debug(
                        f"Vehicle {vehicle_id} detected {obj} in same area, updating obj location"
                    )
                    return (True, obj)
                else:
                    logger.info(f"Ignoring detection, {obj} already found by {d['id']}")
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
        return self.detector.predict(img)


def main():
    """Starts the Gabriel server."""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "--timing", action="store_true", help="Print timing information"
    )

    parser.add_argument("-p", "--port", type=int, default=9099, help="Set port number")

    parser.add_argument(
        "-m",
        "--model",
        default="coco",
        help="(OBJECT DETECTION) Subdirectory under /openscout/server/model/ which contains Tensorflow model to load initially.",
    )

    parser.add_argument(
        "-r", "--threshold", type=float, default=0.85, help="Confidence threshold"
    )

    parser.add_argument(
        "-s",
        "--store",
        action="store_true",
        default=False,
        help="Store images with bounding boxes",
    )

    parser.add_argument(
        "-g",
        "--gabriel",
        default="gabriel-server:5555",
        help="Gabriel server endpoint.",
    )

    parser.add_argument(
        "-src",
        "--source",
        default="telemetry",
        help="Source for engine to register with.",
    )

    parser.add_argument(
        "-x",
        "--exclude",
        help="Comma separated list of classes (ids) to exclude when performing detection. Consult model/<model_name>/label_map.pbtxt.",
    )

    parser.add_argument(
        "-R",
        "--redis",
        type=int,
        default=6379,
        help="Set port number for redis connection [default: 6379]",
    )

    parser.add_argument("-a", "--auth", default="", help="Share key for redis user.")

    parser.add_argument(
        "-hsv",
        "--hsv_threshold",
        type=float,
        default=5.0,
        help="HSV filter threshold [0.0-100.0]",
    )

    parser.add_argument(
        "--radius",
        type=float,
        default=5.0,
        help="Radius in meters to consider when looking for previously found objects.",
    )

    parser.add_argument(
        "--ttl",
        type=int,
        default=1200,
        help="TTL in seconds before objects are cleaned up in redis [default: 1200]",
    )

    parser.add_argument(
        "--geofence",
        default="geofence.kml",
        help="Path to KML file on the shared volume that specified the geofence. [default: geofence.kml]",
    )

    parser.add_argument(
        "--geofence_enabled",
        action="store_true",
        default=False,
        help="Whether to use a geofence to decide whether to store detections",
    )

    parser.add_argument(
        "--unittest",
        action="store_true",
        default=False,
        help="When enabled, will not connect to redis nor store images to disk",
    )

    args, _ = parser.parse_known_args()

    def engine_factory():
        return OpenScoutObjectEngine(args)

    engine = local_engine.LocalEngine(
        engine_factory,
        input_queue_maxsize=60,
        port=args.port,
        num_tokens=2,
        engine_id="openscout-object",
        use_zeromq=True,
    )

    engine.run()


if __name__ == "__main__":
    main()
