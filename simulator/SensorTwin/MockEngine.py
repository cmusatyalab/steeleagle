import time
import os
import cv2
import numpy as np
import logging
import protocol.common_pb2 as common
import protocol.controlplane_pb2 as control_plane
import protocol.gabriel_extras_pb2 as gabriel_extras
import redis 
from PIL import Image, ImageDraw
from pykml import parser
from pygeodesy.sphericalNvector import LatLon

logger = logging.getLogger(__name__)

class MockEngine():
    ENGINE_NAME = "mock_detection_engine"
    
    def __init__(self, args):
        self.threshold = args.threshold
        self.store_detections = args.store
        self.model = args.model # Currently unused
        self.drone_type = args.drone
        self.r = redis.Redis(host='redis', port=args.redis, username='steeleagle', password=f'{args.auth}', decode_responses=True)
        self.r.ping()
        logger.info(f"Connected to redis on port {args.redis}...")
        #timing vars
        self.count = 0
        self.lasttime = time.time()
        self.lastcount = 0
        self.lastprint = self.lasttime
        self.search_radius = args.radius
        self.ttl_secs = args.ttl
        self.geofence = []
        self.geofence_enabled = args.geofence_enabled

        # TODO update to the appropriate project directory - probably not cwd/pwd from simulator
        fence_path = os.getcwd() + "/geofence/" + args.geofence
        if not os.path.exists(fence_path) or not os.path.isfile(fence_path):
            logger.error(f"Geofence KML file not found or is not a file: {fence_path}")
        else:
            # Build geofence from coordinates inside Polygon element of KML file
            with open(f"{fence_path}", 'r', encoding='utf-8') as f:
                root = parser.parse(f).getroot()
                coords = root.Document.Placemark.Polygon.outerBoundaryIs.LinearRing.coordinates.text
                for c in coords.split():
                    lon, lat, alt = c.split(",")
                    p = LatLon(lat, lon)
                    self.geofence.append(p)
            
            logger.info(f"GeoFence read: {self.geofence}")

        if args.exclude:
            self.exclusions = list(map(int, args.exclude.split(",")))
            logger.info("Excluding the following class ids: {}".format(self.exclusions))
        else:
            self.exclusions = None
        
        if self.store_detections:
            # TODO update to appropriate project directory path
            self.watermark = Image.open(os.getcwd() + "/watermark.png")
            self.storage_path = os.getcwd() + "/images"
            try:
                os.makedirs(self.storage_path + "/detected")
            except FileExistsError:
                logger.info("Images directory already exists.")
            logger.info("Storing detection images at {}".format(self.storage_path))

            self.drone_storage_path = os.path.join(self.storage_path, "detected", "drones")
            self.class_storage_path = os.path.join(self.storage_path, "detected", "classes")
            try:
                os.makedirs(self.drone_storage_path)
                os.makedirs(self.class_storage_path)
            except FileExistsError:
                pass

        logger.info(f"Search radius when considering duplicate detections: {self.search_radius}")
        logger.info("SensorTwin mock engine initialized...")

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

    def store_detection_disk(self, im_bgr, filename, drone_id, uniq_classes):
        drone_dir = os.path.join(self.drone_storage_path, drone_id)

        if not os.path.exists(drone_dir):
            os.makedirs(drone_dir)
        
        # Save to drone specific directory
        drone_dir_path = os.path.join(drone_dir, filename)
        im_rgb = Image.fromarray(im_bgr[..., ::-1]) # RGB-order PIL image
        im_rgb.save(drone_dir_path)
        logger.debug(f"Stored image: {drone_dir_path}")

        path = os.path.join(drone_dir, "latest.jpg")
        im_rgb.save(path)
        logger.debug(f"Stored image: {path}")

        for cls in uniq_classes:
            # Save by class directory
            class_dir = os.path.join(self.class_storage_path, cls)
            if not os.path.exists(class_dir):
                os.makedirs(class_dir)
            path = os.path.join(class_dir, filename)
            logger.debug(f"Stored image: {path}")

            os.symlink(drone_dir_path, path)

    def process_image(self, image, sim_results):
        self.t0 = time.time()
        np_data = np.fromstring(image, dtype=np.uint8)
        img = cv2.imdecode(np_data, cv2.IMREAD_COLOR)

        self.t1 = time.time()
        return sim_results, img
    
    def geofilter_passed(self, detection):
        cls = detection["class"]
        drone_id = detection["id"]

        # Check for matches within geosearch radius
        objects = self.r.geosearch(
            "detections",
            longitude=detection["lon"],
            latitude=detection["lat"],
            radius=self.search_radius,
            unit="m"
        )
        if len(objects) == 0:
            logger.info(f"Adding detection for {cls} for drone {drone_id} for the first time")
            return (True, None)
        
        logger.info(f"Objects already exist within search radius: {objects}")

        for obj in objects:
            d = self.r.hgetall(f"objects:{obj}")
            if d and d["cls"] == cls:
                if d["drone_id"] == drone_id:
                    logger.debug(f"Drone {d['drone_id']} detected {obj} in same area, updating obj location")
                    return (True, obj)
                else:
                    logger.info(f"Ignoring detection, {obj} already found by drone {d['drone_id']}")
                    return (False, None)
        return (True, None)

    def process_results(self, image_np, results, cpt_config, telemetry, drone_id):
        pass

    def handle(self, input_frame):
        pass