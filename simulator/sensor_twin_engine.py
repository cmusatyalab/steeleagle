import os
import sys
import time
import asyncio
import logging
from PIL import Image, ImageDraw
import redis
import json
import ultralytics
import numpy as np

from Viewport import Viewport
from DetectionObject import DetectionObject
from st_utilities import Coordinate
import st_utilities

from gabriel_server import cognitive_engine
from gabriel_protocol import gabriel_pb2
import protocol.common_pb2 as common
import protocol.controlplane_pb2 as control_plane
import protocol.gabriel_extras_pb2 as gabriel_extras

DETOBJ_FEATURE_COUNT = 11
BBOX_PLACEHOLDER = 25

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class SensorTwinEngine():
    
    ##################
    # INITIALIZATION #
    ##################

    def __init__(self, args):
        self.ENGINE_NAME = "SensorTwin"
        self.origin = None
        self.detection_object_list = None
        self.viewport_list = None
        if not self.parse_init_file(args.init_file):
            logger.error("Failed to parse init file. Terminating sensorTwin...")
            sys.exit()

        self.store_detections = args.store
        self.threshold = args.threshold
        self.ttl_secs = args.ttl
        self.r = redis.Redis(host='redis', port=args.redis, username='steeleagle', password=f'{args.auth}', decode_repsonses=True)
        self.r.ping()
        self.active = True

        #asyncio.run(self.event_loop(update_interval=1))

    def parse_init_file(self, init_file):
        try:
            with open(init_file) as file:
                data = json.load(file)
        except Exception as e:
            logger.error(f"Exception {e} thrown during init file object extraction")
            logger.error("Failed to extract json data from init file...")
            return False
        origin, fail_flag = self.parse_origin(data['origin'])
        if fail_flag:
            logger.error("Failed init due to incorrectly formatted origin object in init file...")
        drones = data['drones']
        objects = data['objects']
        for items in drones:
            if not self.validate_drone_inputs(drones):
                logger.error("Failed init due to incorrectly formatted drone objects in init file...")
                fail_flag = True
        label_list = []
        for items in objects:
            if items['class_label'] not in label_list:
                label_list.append(items['class_label'])
            if not self.validate_object_inputs(objects):
                logger.error("Failed init due to incorrectly formatted detection objects in init file...")
                fail_flag = True
        if fail_flag:
            return False
        
        self.set_viewport_objects(drones, origin)
        self.set_detection_objects(objects)
        self.set_detection_classes(label_list)
    
    def parse_origin(self, json_origin):
        '''
        Calling function sets a failure flag to prevent early termination while parsing input file.
        Return value of True indicates failure to parse, occurs when a key:value pair for lat, long,
        or alt is missing in the extracted dictionary.
        '''
        if 'lat' not in json_origin or 'lon' not in json_origin or 'alt' not in json_origin:
            return (None, True)
        origin = Coordinate(json_origin['lat'], json_origin['lon'], json_origin['alt'])
        return (origin, False)

    def validate_drone_inputs(self, json_drone_list):
        failure_list = []
        counter = 1
        for items in json_drone_list:
            print(items)
            missing_fov = 0
            fail_flag = False
            if "drone_name" not in items or type(items["drone_name"]) != str:
                logger.error(f"Invalid drone_name during drone validation. Expected name in string form, received {type(items["drone_name"])}")
                fail_flag = True
            if "x_offset" not in items or (type(items["x_offset"]) != float and type(items["x_offset"]) != int):
                logger.error(f"Invalid x_offset during drone validation. Expected int or float, received {type(items["x_offset"])}")
                fail_flag = True
            if "y_offset" not in items or (type(items["y_offset"]) != float and type(items["y_offset"]) != int):
                logger.error(f"Invalid y_offset during drone validation. Expected int or float, received {type(items["y_offset"])}")
                fail_flag = True
            if "z_offset" not in items or (type(items["z_offset"]) != float and type(items["z_offset"]) != int):
                logger.error(f"Invalid z_offset during drone validation. Expected int or float, received {type(items["z_offset"])}")
                fail_flag = True
            if "orientation" not in items or type(items["orientation"]) != int:
                logger.error(f"Invalid orientation during drone validation. Expected int, received {type(items["orientation"])}")
                fail_flag = True
            if "gimbal_rotation" not in items or type(items["gimbal_rotation"]) != int:
                logger.error(f"Invalid gimbal rotation during drone validation. Expected int, received {type(items["gimbal_rotation"])}")
                fail_flag = True
            if "hfov" not in items or (type(items["hfov"]) != int and type(items["hfov"]) != float):
                logger.warning(f"No HFOV provided for drone_{counter}...")
                missing_fov += 1
            if "vfov" not in items or (type(items["vfov"]) != int and type(items["vfov"]) != float):
                logger.warning(f"No VFOV provided for drone_{counter}...")
                missing_fov += 1
            if "dfov" not in items or (type(items["dfov"]) != int and type(items["dfov"]) != float):
                logger.warning(f"No DFOV provided for drone_{counter}...")
                missing_fov += 1
            if missing_fov > 1:
                logger.error(f"Invalid FOV specifications during drone validation. Expected 2 of 3 of HFOV, VFOV, DFOV...")
                fail_flag = True
            if fail_flag:
                failure_list.append(f"drone_{counter}")
            counter += 1
        if len(failure_list) != 0:
            logger.error("Failed to validate json inputs for drones...")
            logger.error(f"Drones failing initialization: {", ".join(failure_list)}")
            return False
        else:
            logger.info("Successfully validated drone json inputs...")
            return True

    def validate_object_inputs(self, json_object_list):
        failure_list = []
        counter = 1
        for items in json_object_list:
            fail_flag = False
            if "object_name" not in items or type(items["object_name"]) != str:
                logger.error(f"Invalid object name during detection object validation for object {counter}. Expected string, received {type(items["object_name"])}")
                fail_flag = True
            if "class_label" not in items or type(items["class_label"]) != str:
                logger.error(f"Invalid class label during detection object validation for object {counter}. Expected string, received {type(items["class_label"])}")
                fail_flag = True
            if "base_confidence" not in items or (type(items["base_confidence"]) != float and type(items["base_confidence"]) != int):
                logger.error(f"Invalid base confidence during detection object validation for object {counter}. Expected float, received {type(items["base_confidence"])}")
                fail_flag = True
            if "falloff_start_distance" not in items or (type(items["falloff_start_distance"]) != float and type(items["falloff_start_distance"]) != int):
                logger.error(f"Invalid falloff starting distance during detection object validation for object {counter}. Expected float or int, received {type(items["falloff_start_distance"])}")
                fail_flag = True
            if "object_length" not in items or (type(items["object_length"]) != float and type(items["object_length"]) != int):
                logger.error(f"Invalid object length during detection object validation for object {counter}. Expected float or int, received {type(items["object_length"])}")
                fail_flag = True
            if "object_width" not in items or (type(items["object_width"]) != float and type(items["object_width"]) != int):
                logger.error(f"Invalid object width during detection object validation for object {counter}. Expected float or int, received {type(items["object_width"])}")
                fail_flag = True
            if "object_height" not in items or (type(items["object_height"]) != float and type(items["object_height"]) != int):
                logger.error(f"Invalid object height during detection object validation for object {counter}. Expected float or int, received {type(items["object_height"])}")
                fail_flag = True
            if "x_offset" not in items or (type(items["x_offset"]) != float and type(items["x_offset"]) != int):
                logger.error(f"Invalid x offset during detection object validation for object {counter}. Expected float or int, received {type(items["x_offset"])}")
                fail_flag = True
            if "y_offset" not in items or (type(items["y_offset"]) != float and type(items["y_offset"]) != int):
                logger.error(f"Invalid y offset during detection object validation for object {counter}. Expected float or int, received {type(items["y_offset"])}")
                fail_flag = True
            if "z_offset" not in items or (type(items["z_offset"]) != float and type(items["z_offset"]) != int):
                logger.error(f"Invalid z offset during detection object validation for object {counter}. Expected float or int, received {type(items["z_offset"])}")
                fail_flag = True
            if fail_flag:
                failure_list.append(f"object_{counter}")
            counter += 1
        
        if len(failure_list) != 0:
            logger.error("Failed to validate json inputs for detection objects...")
            logger.error(f"Objects failing initialization: {", ".join(failure_list)}")
            return False
        else:
            logger.info("Successfully validated detection object json inputs...")
            return True

    def create_detection_object(self, raw_det_obj):
        if len(raw_det_obj) <= DETOBJ_FEATURE_COUNT:
            logger.error(f"Attempted to produce detection object from improperly formatted values. Expected {DETOBJ_FEATURE_COUNT}, raw object contained {len(raw_det_obj)}")
            return None
        return DetectionObject(
            object_name=raw_det_obj['object_name'],
            x=raw_det_obj['x_offset'],
            y=raw_det_obj['y_offset'],
            alt=raw_det_obj['z_offset'],
            label=raw_det_obj['class_label'],
            base_conf=raw_det_obj['base_confidence'],
            falloff_rate=raw_det_obj['falloff_rate'],
            falloff_dist=raw_det_obj['falloff_start_distance'],
            length=raw_det_obj['object_length'],
            width=raw_det_obj['object_width'],
            height=raw_det_obj['object_height']
        )

    def create_viewport(self, raw_vp_dict, origin: Coordinate):
        vp = Viewport(
            raw_vp_dict['drone_name'],
            raw_vp_dict['drone_type'],
            Coordinate(raw_vp_dict["x_offset"], raw_vp_dict["y_offset"], raw_vp_dict["z_offset"]),
            raw_vp_dict["orientation"],
            raw_vp_dict["gimbal_rotation"],
            origin
        )
        
        if "horizontal_fov" in raw_vp_dict:
            vp.set_hfov(raw_vp_dict["horizontal_fov"])
        if "vertical_fov" in raw_vp_dict:
            vp.set_vfov(raw_vp_dict["vertical_fov"])
        if "diagonal_fov" in raw_vp_dict:
            vp.set_dfov(raw_vp_dict["diagonal_fov"])
        if vp.horizontal_fov == None:
            vp.derive_hfov()
        if vp.vertical_fov == None:
            vp.derive_vfov()
        if vp.diagonal_fov == None:
            vp.derive_dfov()
        vp.derive_aspect_ratio()

        if vp.horizontal_fov == None or vp.vertical_fov == None or vp.diagonal_fov == None:
            logger.error(f"Failed to specify at least two of three FOV widths. Received "
                        f"HFOV: {vp.horizontal_fov}, VFOV: {vp.vertical_fov}, DFOV: {vp.diagonal_fov}")
            logger.error("Failed to initialize viewport for simulation")
            return None

        vp.update_bounding_box()
        return vp

    def set_viewport_objects(self, vp_list: list[Viewport]):
        return {vp.drone_name: vp for vp in vp_list}

    def set_detection_objects(self, objects_list: list[DetectionObject]):
        return {obj.object_name: obj for obj in objects_list}

    def set_detection_classes(self, labels_list):
        pass
    

    ####################
    # ENGINE OPERATION #
    ####################

    async def event_loop(self, update_interval):
        '''
        Eventually intended for traces that involve changing detection object positions
        '''
        while self.active:
            self.t_start = time.time()
            #await self.update_objects()
            # detection check and image return for all viewports
            # sleep for update_interval - time elapsed since start
            await asyncio.sleep(update_interval - (time.time() - self.t_start))

    def handle(self, input_frame):
        '''
        Expecting a compute request here, similar to object detection engine
        '''
        if input_frame.payload_type == gabriel_pb2.PayloadType.TEXT:
            # Ignore TEXT requests
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
                extras.drone_name
            )

            if gabriel_result is not None:
                result_wrapper.results.append(gabriel_result)
        
        response = control_plane.Response()
        response.seq_num = extras.cpt_request.seq_num
        response.timestamp.GetCurrentTime()
        response.resp = common.ResponseStatus.OK
        result_wrapper.extras.Pack(response)

        self.t1 = time.time()
        return result_wrapper

    def update_viewport(self, drone_name: str, telemetry):
        if not telemetry.HasField('global_position'):
            logger.error(f"Telemetry packet received without global position field for {drone_name}")
        loc = Coordinate(telemetry.global_position.longitude, telemetry.global_position.latitude, telemetry.global_position.altitude)
        self.viewport_list[drone_name].set_global_position(loc)
        logger.debug(f"Set viewport for {drone_name} to global position {self.viewport_list[drone_name].get_global_position()} at time {time.time()}")

    def update_detection_object(self, object_name: str, new_pos: Coordinate):
        self.detection_object_list[object_name].set_global_pos(new_pos.long, new_pos.lat, new_pos.alt)
        logger.debug(f"Set {object_name} to global position {self.detection_object_list[object_name].get_global_pos()} at time {time.time()}")

    ################################
    # IMAGE/DETECTION MANIPULATION #
    ################################

    def process_image(self, image, image_path, drone_name):
        vp = self.viewport_list[drone_name]
        detections = [x.produce_detection(vp.get_global_position()) for x in self.detection_object_list if vp.check_object(x)]
        nd_image = np.asarray(image)
        if len(detections) == 0:
            # Returns a result containing the base image with no associated bounding boxes/detections
            return self.produce_simulated_result(nd_image, image_path, self.class_names, None)

        boxes = []
        for det in detections:
            if det[1] >= self.threshold:
                boxes.append(self.detection_to_bounding_box(det[0], det[1]))
        
        result = self.produce_simulated_result(nd_image, image_path, self.class_names, boxes)
        return result

    def detection_to_bounding_box(self, class_label: str, confidence: float, image_height: int, image_width: int) -> ultralytics.engine.results.Boxes:
        c_height = image_height / 2
        c_width = image_width / 2
        x1 = max(0, min(image_width, c_width - BBOX_PLACEHOLDER))
        x2 = max(0, min(image_width, c_width + BBOX_PLACEHOLDER))
        y1 = max(0, min(image_height, c_height - BBOX_PLACEHOLDER))
        y2 = max(0, min(image_height, c_height + BBOX_PLACEHOLDER))
        # TODO - model the location of the box against the actual image properply using perspective projection
        # box_values = perspective_projection_conversion(detection_object, viewport)
        box = ultralytics.engine.results.Boxes([x1, y1, x2, y2, confidence, class_label], (image_height, image_width))
        return box

    def produce_simulated_result(self, image: np.ndarray, path: str, class_names: dict, boxes: list[ultralytics.engine.results.Boxes] | None) -> ultralytics.engine.results.Results:
        return ultralytics.engine.results.Results(image, path, class_names, boxes)

    def store_detection_db(self, drone_name: str, lat: float, lon: float, class_label: str, confidence: float, link="", object_name=None):
        # Assign object random name if not given
        if object_name is None:
            object_name = f"{class_label}-{os.urandom(2).hex()}"
        self.r.geoadd("detections", [lon, lat, object_name])

        object_key = f"objects:{object_name}"
        self.r.hset(object_key, "last_seen", f"{time.time()}")
        self.r.hset(object_key, "drone_id", f"{drone_name}")
        self.r.hset(object_key, "cls", f"{class_label}")
        self.r.hset(object_key, "confidence", f"{confidence}")
        self.r.hset(object_key, "link", f"{link}")
        self.r.hset(object_key, "longitude", f"{lon}")
        self.r.hset(object_key, "latitude", f"{lat}")
        self.r.expire(object_key, self.ttl_secs)
        logger.debug(f"Updating {object_key} status: last_seen: {time.time()}")

    def store_detection_disk(self, im_bgr, filename, drone_id, uniq_classes):
        drone_dir = os.path.join(self.drone_storage_path, drone_id)
        if not os.path.exists(drone_dir):
            os.makedirs(drone_dir)

        drone_dir_path = os.path.join(drone_dir, filename)
        im_rgb = Image.fromarray(im_bgr[..., ::-1])
        im_rgb.save(drone_dir_path)
        logger.debug(f"Stored image: {drone_dir_path}")

        path = os.path.join(drone_dir, "latest.jpg")
        im_rgb.save(path)
        logger.debug(f"Stored image: {path}")

        for cls in uniq_classes:
            class_dir = os.path.join(self.class_storage_path, cls)
            if not os.path.exists(class_dir):
                os.makedirs(class_dir)
            path = os.path.join(class_dir, filename)
            logger.debug(f"Stored image: {path}")
            os.symlink(drone_dir_path, path)

    def send_result(self, viewport, result):
        pass