# Copyright (C) 2020 Carnegie Mellon University
# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import base64
import time
import os
import cv2
import numpy as np
import logging
from gabriel_server import cognitive_engine
from gabriel_protocol import gabriel_pb2
from cnc_protocol import cnc_pb2
from io import BytesIO
from PIL import Image, ImageDraw
import tensorflow as tf 
tf.compat.v1.enable_eager_execution() 
from object_detection.utils import ops as utils_ops
from object_detection.utils import label_map_util
from object_detection.utils import visualization_utils as vis_util

#PATCHES
# patch tf1 into `utils.ops`
utils_ops.tf = tf.compat.v2

# Patch the location of gfile
tf.gfile = tf.io.gfile

#tf.get_logger().warning('test')
# WARNING:tensorflow:test
tf.get_logger().setLevel('ERROR')

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

detection_log = logging.getLogger("object-engine")
fh = logging.FileHandler('/openscout/server/openscout-object-engine.log')
fh.setLevel(logging.INFO)
formatter = logging.Formatter('%(message)s')
fh.setFormatter(formatter)
detection_log.addHandler(fh)

class TFPredictor():
    def __init__(self,model_path): 
        model_name = model_path+'/saved_model'
        label_map_file_path = model_path+'/label_map.pbtxt'
        logger.info(tf.config.experimental.list_physical_devices())
        self.detection_model = self.load_model(model_name)
        self.category_index = label_map_util.create_category_index_from_labelmap(label_map_file_path, use_display_name=True) 
        self.output_dict = None
        
    def load_model(self,model_dir):   
        model = tf.compat.v2.saved_model.load(export_dir=str(model_dir), tags=None)
        model = model.signatures['serving_default'] 
        return model 
    
    def infer(self, image):  
        image = np.asarray(image)  
        # The input needs to be a tensor, convert it using `tf.convert_to_tensor`.
        input_tensor = tf.convert_to_tensor(image)
        # The model expects a batch of images, so add an axis with `tf.newaxis`.
        input_tensor = input_tensor[tf.newaxis,...]

        # Run inference
        output_dict = self.detection_model(input_tensor)
        num_detections = int(output_dict.pop('num_detections'))
        output_dict = {key:value[0, :num_detections].numpy() 
                         for key,value in output_dict.items()}
        output_dict['num_detections'] = num_detections

          # detection_classes should be ints.
        output_dict['detection_classes'] = output_dict['detection_classes'].astype(np.int64)

          # Handle models with masks:
        if 'detection_masks' in output_dict:
          # Reframe the the bbox mask to the image size.
          detection_masks_reframed = utils_ops.reframe_box_masks_to_image_masks(
                    output_dict['detection_masks'], output_dict['detection_boxes'],
                     image.shape[0], image.shape[1])
          detection_masks_reframed = tf.cast(detection_masks_reframed > 0.5,
                                               tf.uint8)
          output_dict['detection_masks_reframed'] = detection_masks_reframed.numpy()

        self.output_dict = output_dict
        return output_dict

class DroneComputeEngine(cognitive_engine.Engine):
    ENGINE_NAME = "compute"

    def __init__(self, args):
        self.detector = TFPredictor(args.model)
        self.threshold = args.threshold
        self.store_detections = args.store

        if args.exclude:
            self.exclusions = list(map(int, args.exclude.split(","))) #split string to int list
            logger.info("Excluding the following class ids: {}".format(self.exclusions))
        else:
            self.exclusions = None

        logger.info("TensorFlowPredictor initialized with the following model path: {}".format(args.model))
        logger.info("Confidence Threshold: {}".format(self.threshold))

        if self.store_detections:
            self.watermark = Image.open(os.getcwd()+"/watermark.png")
            self.storage_path = os.getcwd()+"/images/"
            try:
                os.mkdir(self.storage_path)
            except FileExistsError:
                logger.info("Images directory already exists.")
            logger.info("Storing detection images at {}".format(self.storage_path))


    def handle(self, input_frame):
        if input_frame.payload_type != gabriel_pb2.PayloadType.IMAGE:
            status = gabriel_pb2.ResultWrapper.Status.WRONG_INPUT_FORMAT
            return cognitive_engine.create_result_wrapper(status)

        extras = cognitive_engine.unpack_extras(openscout_pb2.Extras, input_frame)
        output_dict, image_np = self.process_image(input_frame.payloads[0])

        status = gabriel_pb2.ResultWrapper.Status.SUCCESS
        result_wrapper = cognitive_engine.create_result_wrapper(status)
        result_wrapper.result_producer_name.value = self.ENGINE_NAME

        if self.store_detections:
            try:
                vis_util.visualize_boxes_and_labels_on_image_array(
                    image_np,
                    np.squeeze(output_dict['detection_boxes']),
                    np.squeeze(output_dict['detection_classes']),
                    np.squeeze(output_dict['detection_scores']),
                    self.detector.category_index,
                    use_normalized_coordinates=True,
                    min_score_thresh=self.threshold,
                    line_thickness=4)

                img = Image.fromarray(image_np)
                draw = ImageDraw.Draw(img)
                draw.bitmap((0,0), self.watermark, fill=None)
                bio = BytesIO()
                img.save(bio, format="JPEG")
                filename = str(time.time()) + ".png"
                path = self.storage_path + filename
            except IndexError as e:
                logger.error(e)

        if output_dict['num_detections'] > 0:
            #convert numpy arrays to python lists
            classes = output_dict['detection_classes'].tolist()
            boxes = output_dict['detection_boxes'].tolist()
            scores = output_dict['detection_scores'].tolist()

            result = gabriel_pb2.ResultWrapper.Result()
            result.payload_type = gabriel_pb2.PayloadType.TEXT

            detections_above_threshold = False
            r = ""
            for i in range(0, len(classes)):
                if(scores[i] > self.threshold):
                    if self.exclusions is None or classes[i] not in self.exclusions:
                        detections_above_threshold = True
                        logger.info("Detected : {} - Score: {:.3f}".format(self.detector.category_index[classes[i]]['name'],scores[i]))
                        if i > 0:
                            r += ", "
                        r += "Detected {} ({:.3f})".format(self.detector.category_index[classes[i]]['name'],scores[i])
                        if self.store_detections:
                            detection_log.info("{},{},{},{},{:.3f},{}".format(extras.client_id, extras.location.latitude, extras.location.longitude, self.detector.category_index[classes[i]]['name'],scores[i], os.environ["WEBSERVER"]+"/"+filename))
                        else:
                            detection_log.info("{},{},{},{},{:.3f},".format(extras.client_id, extras.location.latitude, extras.location.longitude, self.detector.category_index[classes[i]]['name'], scores[i]))

            if detections_above_threshold:
                result.payload = r.encode(encoding="utf-8")
                result_wrapper.results.append(result)

                if self.store_detections:
                    logger.info("Stored image: {}".format(path))
                    img.save(path)

        return result_wrapper

    def process_image(self, image):
        np_data = np.fromstring(image, dtype=np.uint8)
        img = cv2.imdecode(np_data, cv2.IMREAD_COLOR)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        output_dict = self.inference(img)
        return output_dict, img

    def inference(self, img):
        """Allow timing engine to override this"""
        return self.detector.infer(img)

