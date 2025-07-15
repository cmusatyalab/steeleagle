import time
import os
import logging
import numpy as np
import json
from st_utilities import Coordinate
import st_utilities
from Viewport import Viewport
from DetectionObject import DetectionObject
#from MockEngine import MockEngine
import ultralytics
import zmq
import asyncio

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

FALLOFF_PENALTY = 10.0
DETOBJ_FEATURE_COUNT = 7
CLASS_DICT = {0: "Car", 1: "Person"}

'''
ST File Requirements:
- Origin Position
- Tileset w/ GPS mappings
- X & Y Dimension Lengths
- Drone Model
- Field of View
- Zoom Level
- Target List
    - X & Y Coords
    - Distance Magnitude to Confidence
        - Either modeling function or step function with thresholds and concrete values

Prototype Assumptions:
- Search area is perfectly flat, drone altitude is only var in z-plane
- Square/rectangular tiles
- Focal length is fixed
- Gimbal fixed at single angle?
- SensorTwin replaces detection engine instead of interposing it
- Rectangular bounding boxes
- Detections & confidence intervals are deterministic, not probabilistic

Design Questions
- Expected usage requires full end-to-end? Or simulated Redis/other component access?
- Toy/unit tests for rapid validation of draft sensortwin files?
'''

class SensorTwinEngine():
    def __init__(self, args):
        self.origin = None
        self.detection_object_list = None
        self.viewport_list = None
        self.mock_engine = None
        self.telemetry_retriever = None

    def parse_init_file(self, init_file):
        try:
            with open(init_file) as file:
                data = json.load(file)
        except Exception as e:
            logger.error(f"Exception {e} thrown during init file object extraction")
            logger.error("Failed to extract json data from init file...")
            return False
        origin, fail_flag = parse_origin(data['origin'])
        if fail_flag:
            logger.error("Failed init due to incorrectly formatted origin object in init file...")
        drones = data['drones']
        objects = data['objects']
        for items in drones:
            if not validate_drone_inputs(drones):
                logger.error("Failed init due to incorrectly formatted drone objects in init file...")
                fail_flag = True
        label_list = []
        for items in objects:
            if items['class_label'] not in label_list:
                label_list.append(items['class_label'])
            if not validate_object_inputs(objects):
                logger.error("Failed init due to incorrectly formatted detection objects in init file...")
                fail_flag = True
        if fail_flag:
            return False
        
        self.set_viewport_objects(drones, origin)
        self.set_detection_objects(objects)
        self.set_detection_classes(label_list)

    def set_detection_objects(self, raw_object_list):
        if len(raw_object_list) == 0:
            self.obj_list = None
            logger.warning("No detection objects received during simulation initialization...")
        else:
            self.obj_list = [create_detection_object(x) for x in raw_object_list]

    def set_detection_classes(self, raw_class_list: list[str]):
        if len(raw_class_list) == 0:
            self.class_list = None
            logger.warning("No detection classes received during initialization...")
        else:
            self.class_list = raw_class_list
    
    def set_viewport_objects(self, raw_vp_list, origin):
        if len(raw_vp_list) == 0:
            logger.error("No viewports received during simulation initialization...")
        else:
            self.viewport_list = [create_viewport(x, origin) for x in raw_vp_list]

    def check_detections(self):
        for vp in self.viewport_list:
            detections = [x.produce_detection(vp.get_global_position()) for x in self.obj_list if vp.check_object(x)]
            boxes = produce_boxes(vp, detections)
            result = produce_result(boxes)
            # Send result back to corresponding drone socket

    def update_viewport_position(self, viewport_id):
        # Needs to request current telemetry from either redis or the corresponding drone
        pass

def parse_origin(json_origin):
    if 'lat' not in json_origin or 'lon' not in json_origin:
        return (None, True)
    return (st_utilities.wgs_to_cartesian(json_origin['lat'], json_origin['lon']), False) #TODO fix origin initialization

def validate_drone_inputs(json_drone_list):
    failure_list = []
    counter = 1
    for items in json_drone_list:
        print(items)
        missing_fov = 0
        fail_flag = False
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

def validate_object_inputs(json_object_list):
    failure_list = []
    counter = 1
    for items in json_object_list:
        fail_flag = False
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


def create_detection_object(raw_det_obj):
    if len(raw_det_obj) <= DETOBJ_FEATURE_COUNT:
        logger.error(f"Attempted to produce detection object from improperly formatted values. Expected {DETOBJ_FEATURE_COUNT}, raw object contained {len(raw_det_obj)}")
        return None
    return DetectionObject(
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

def create_viewport(raw_vp_dict, origin: Coordinate):
    
    vp = Viewport(
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

def produce_boxes(vp: Viewport, detection_list: tuple[str, float]) -> ultralytics.engine.results.Boxes:
    # For each object, perspective projection from world space to camera space
    
    boxes = [ultralytics.engine.results.Boxes() for x in detection_list]
    pass

def produce_result(base_image: np.ndarray, image_path: str, box_list: list[ultralytics.engine.results.Boxes]) -> ultralytics.engine.results.Results:
    # Receive class, confidence
    # Position box?
    # Box init - (x1, y1, x2, y2, conf, class, track_id [optional])
    return ultralytics.engine.results.Results(base_image, image_path, CLASS_DICT, boxes=box_list)

def main():
    logger.info("Starting sensor twin...")
    test_st = SensorTwinEngine("")
    test_st.parse_init_file("testfiles/st_init.json")
    logger.info("Completed sensor twin test...")

if __name__ == "__main__":
    main()
