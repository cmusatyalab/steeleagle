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
import protocol.dataplane_pb2 as dataplane
import protocol.common_pb2 as common
from PIL import Image, ImageDraw
import json
import torch
import redis

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class MidasAvoidanceEngine(cognitive_engine.Engine):
    ENGINE_NAME = "obstacle-avoidance"


    def __init__(self, args):
        self.threshold = args.threshold # default should be 190
        self.store_detections = args.store
        self.model = args.model
        self.valid_models = ['DPT_BEiT_L_512',
                'DPT_BEiT_L_384',
                'DPT_SwinV2_L_384',
                'DPT_SwinV2_B_384',
                'DPT_SwinV2_T_256',
                'DPT_Swin_L_384',
                'DPT_Next_ViT_L_384',
                'DPT_LeViT_224',
                'DPT_Large',
                'DPT_Hybrid',
                'MiDaS',
                'MiDaS_small']
        self.r = redis.Redis(host='redis', port=args.redis, username='steeleagle', password=f'{args.auth}',decode_responses=True)
        self.r.ping()
        logger.info(f"Connected to redis on port {args.redis}...")
        #timing vars
        self.count = 0
        self.lasttime = time.time()
        self.lastcount = 0
        self.lastprint = self.lasttime
        self.faux = args.faux
        if self.faux:
            self.storage_path = os.getcwd()+"/images/"
            logger.info("Generating faux actutations from  {}".format(self.storage_path + "/actuations.txt"))
            self.actuations_fd = open(self.storage_path + "/actuations.txt", mode='r')

        self.load_midas(self.model)

        if self.store_detections:
            self.watermark = Image.open(os.getcwd()+"/watermark.png")
            self.storage_path = os.getcwd()+"/images/"
            try:
                os.makedirs(self.storage_path+"/moa")
            except FileExistsError:
                logger.info("Images directory already exists.")
            logger.info("Storing detection images at {}".format(self.storage_path))

    def load_midas(self, model):
        logger.info(f"Fetching {self.model} MiDaS model from torch hub...")
        self.detector = torch.hub.load("intel-isl/MiDaS", model)
        self.model = model

        self.device = torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")
        self.detector.to(self.device)
        self.detector.eval()

        midas_transforms = torch.hub.load("intel-isl/MiDaS", "transforms")

        if self.model == "MiDaS_small":
            self.transform = midas_transforms.small_transform
        elif self.model == 'DPT_SwinV2_L_384' or 'DPT_SwinV2_B_384' or 'DPT_Swin_L_384':
            self.transform = midas_transforms.swin384_transform
        elif self.model == "MiDaS":
            self.transform = midas_transforms.default_transform
        elif self.model == "DPT_SwinV2_T_256":
            self.transform = midas_transforms.swin256_transform
        elif self.model == "DPT_LeViT_224":
            self.transform = midas_transforms.levit_transform
        elif self.model == "DPT_BEiT_L_512":
            self.transform = midas_transforms.beit512_transform
        else:
            self.transform = midas_transforms.dpt_transform
        logger.info("Depth predictor initialized with the following model: {}".format(model))
        logger.info("Depth Threshold: {}".format(self.threshold))

    def store_vector(self, drone, vec):
        key = self.r.xadd(
                    f"avoidance",
                    {"drone_id": drone, "vector": vec },
                )

    def handle(self, input_frame):
        if input_frame.payload_type == gabriel_pb2.PayloadType.TEXT:
            #if the payload is TEXT, say from a CNC client, we ignore
            status = gabriel_pb2.ResultWrapper.Status.SUCCESS
            result_wrapper = cognitive_engine.create_result_wrapper(status)
            result_wrapper.result_producer_name.value = self.ENGINE_NAME
            result = gabriel_pb2.ResultWrapper.Result()
            result.payload_type = gabriel_pb2.PayloadType.TEXT
            result.payload = f'Ignoring TEXT payload.'.encode(encoding="utf-8")
            result_wrapper.results.append(result)
            return result_wrapper

        req = cognitive_engine.unpack_extras(dataplane.Request, input_frame)

        if extras.detection_model != '' and extras.detection_model != self.model:
            if extras.detection_model not in self.valid_models:
                logger.error(f"Invalid MiDaS model {extras.detection_model}.")
            else:
                self.load_midas(extras.detection_model)
        self.t0 = time.time()
        vector, depth_img = self.process_image(input_frame.payloads[0])
        timestamp_millis = int(time.time() * 1000)
        status = gabriel_pb2.ResultWrapper.Status.SUCCESS
        result_wrapper = cognitive_engine.create_result_wrapper(status)
        result_wrapper.result_producer_name.value = self.ENGINE_NAME

        result = gabriel_pb2.ResultWrapper.Result()
        result.payload_type = gabriel_pb2.PayloadType.TEXT
        r = []
        r.append({"vector": vector })
        logger.info(f"Vector returned by obstacle avoidance algorithm: {vector}")
        self.store_vector(req.drone_id, vector)
        result.payload = json.dumps(r).encode(encoding="utf-8")
        result_wrapper.results.append(result)
        response = dataplane.Response()
        response.seq_num = req.seq_num
        response.timestamp.GetCurrentTime()
        response.resp= common.ResponseStatus.OK
        response.cpt
        result_wrapper.extras = response

        if self.store_detections:
            filename = str(timestamp_millis) + ".jpg"
            depth_img = Image.fromarray(depth_img)
            draw = ImageDraw.Draw(depth_img)
            draw.bitmap((0,0), self.watermark, fill=None)
            path = self.storage_path + "/moa/" + filename
            depth_img.save(path, format="JPEG")
            path = self.storage_path + "/moa/latest.jpg"
            depth_img.save(path, format="JPEG")
            logger.info("Stored image: {}".format(path))

        self.count += 1
        if self.t1 - self.lastprint > 5:
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

        self.lasttime = self.t1

        return result_wrapper

    def process_image(self, image):
        self.t0 = time.time()
        np_data = np.fromstring(image, dtype=np.uint8)
        img = cv2.imdecode(np_data, cv2.IMREAD_COLOR)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        actuation_vector, depth_img = self.inference(img)
        self.t1 = time.time()
        return actuation_vector, depth_img

    def inference(self, img):
        """Allow timing engine to override this"""
        # Default resolutions of the frame are obtained.The default resolutions are system dependent.
        # We convert the resolutions from float to integer.
        actuation_vector = 0
        frame_width = img.shape[1]
        frame_height = img.shape[0]
        scrapY, scrapX = frame_height//3, frame_width//5

        input_batch = self.transform(img).to(self.device)

        with torch.no_grad():
            prediction = self.detector(input_batch)

            prediction = torch.nn.functional.interpolate(
                prediction.unsqueeze(1),
                size=img.shape[:2],
                mode="bicubic",
                align_corners=False,
            ).squeeze()

        depth_map = prediction.cpu().numpy()

        depth_map = cv2.normalize(depth_map, None, 0, 1, norm_type=cv2.NORM_MINMAX, dtype=cv2.CV_64F)
        depth_map = (depth_map*255).astype(np.uint8)
        full_depth_map = cv2.applyColorMap(depth_map , cv2.COLORMAP_OCEAN)
        
        
        cv2.rectangle(full_depth_map, (scrapX,scrapY), (full_depth_map.shape[1]-scrapX, full_depth_map.shape[0]-scrapY), (255,255,0), thickness=1)
        depth_map[depth_map >= self.threshold] = 0
        depth_map[depth_map != 0] = 255
        depth_map = depth_map[scrapY : frame_height - scrapY, scrapX : frame_width - scrapX]

        # convert the grayscale image to binary image
        ret, thresh = cv2.threshold(depth_map, 254, 255, 0)
        # find contours in the binary image
        contours, h = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        #full_depth_map = cv2.merge(thresh, full_depth_map)
        try:
            c = max(contours, key=cv2.contourArea)
            # calculate moments for each contour
            M = cv2.moments(c)
            cX = int(M["m10"] / M["m00"])
            cY = int(M["m01"] / M["m00"])
            cv2.circle(full_depth_map, (scrapX + cX, scrapY + cY), 5, (0, 255, 0), -1)
            actuation_vector = (scrapX + cX - (full_depth_map.shape[1] / 2) + 1) / ( full_depth_map.shape[1] / 2 - scrapX )
            cv2.putText(full_depth_map, "{:.4f}".format(actuation_vector), (scrapX + cX, scrapY + cY - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        except:
            pass

        if self.faux:
            actuation_vector = self.actuations_fd.readline()
            #if we have reached the end of the fd, seek back to the top
            if actuation_vector == '':
                self.actuations_fd.seek(0)
                actuation_vector = self.actuations_fd.readline()
            actuation_vector = float(actuation_vector.split('\n')[0])
            if actuation_vector == 999:
                time.sleep(5)
        
        return actuation_vector, full_depth_map

class Metric3DAvoidanceEngine(cognitive_engine.Engine):
    ENGINE_NAME = "obstacle-avoidance"


    def __init__(self, args):
        self.threshold = args.threshold # default should be 190
        self.store_detections = args.store
        self.model = args.model
        self.valid_models = ['metric3d_convnext_large', 'metric3d_vit_small', 'metric3d_vit_large', 'metric3d_vit_giant2']
        self.r = redis.Redis(host='redis', port=args.redis, username='steeleagle', password=f'{args.auth}',decode_responses=True)
        self.r.ping()
        logger.info(f"Connected to redis on port {args.redis}...")
        #timing vars
        self.count = 0
        self.lasttime = time.time()
        self.lastcount = 0
        self.lastprint = self.lasttime
        self.faux = args.faux
        if self.faux:
            self.storage_path = os.getcwd()+"/images/"
            logger.info("Generating faux actutations from  {}".format(self.storage_path + "/actuations.txt"))
            self.actuations_fd = open(self.storage_path + "/actuations.txt", mode='r')

        self.load_model(self.model)

        if self.store_detections:
            self.watermark = Image.open(os.getcwd()+"/watermark.png")
            self.storage_path = os.getcwd()+"/images/"
            try:
                os.makedirs(self.storage_path+"/moa")
            except FileExistsError:
                logger.info("Images directory already exists.")
            logger.info("Storing detection images at {}".format(self.storage_path))

    def load_model(self, model):
        logger.info(f"Fetching {self.model} model from torch hub...")
        self.detector = torch.hub.load('yvanyin/metric3d', model)
        self.model = model

        self.device = torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")
        self.detector.to(self.device)
        self.detector.eval()

        logger.info("Depth predictor initialized with the following model: {}".format(model))
        logger.info("Depth Threshold: {}".format(self.threshold))

    def store_vector(self, drone, vec):
        key = self.r.xadd(
                    f"avoidance",
                    {"drone_id": drone, "vector": vec },
                )

    def handle(self, input_frame):
        if input_frame.payload_type == gabriel_pb2.PayloadType.TEXT:
            #if the payload is TEXT, say from a CNC client, we ignore
            status = gabriel_pb2.ResultWrapper.Status.SUCCESS
            result_wrapper = cognitive_engine.create_result_wrapper(status)
            result_wrapper.result_producer_name.value = self.ENGINE_NAME
            result = gabriel_pb2.ResultWrapper.Result()
            result.payload_type = gabriel_pb2.PayloadType.TEXT
            result.payload = f'Ignoring TEXT payload.'.encode(encoding="utf-8")
            result_wrapper.results.append(result)
            return result_wrapper

        extras = cognitive_engine.unpack_extras(cnc_pb2.Extras, input_frame)

        if extras.detection_model != '' and extras.detection_model != self.model:
            if extras.detection_model not in self.valid_models:
                logger.error(f"Invalid model {extras.detection_model}.")
            else:
                self.load_model(extras.detection_model)
        self.t0 = time.time()
        vector, depth_img = self.process_image(input_frame.payloads[0])
        timestamp_millis = int(time.time() * 1000)
        status = gabriel_pb2.ResultWrapper.Status.SUCCESS
        result_wrapper = cognitive_engine.create_result_wrapper(status)
        result_wrapper.result_producer_name.value = self.ENGINE_NAME

        result = gabriel_pb2.ResultWrapper.Result()
        result.payload_type = gabriel_pb2.PayloadType.TEXT
        r = []
        r.append({"vector": vector })
        logger.info(f"Vector returned by obstacle avoidance algorithm: {vector}")
        self.store_vector(extras.drone_id, vector)
        result.payload = json.dumps(r).encode(encoding="utf-8")
        result_wrapper.results.append(result)

        if self.store_detections:
            filename = str(timestamp_millis) + ".jpg"
            depth_img = Image.fromarray(depth_img)
            draw = ImageDraw.Draw(depth_img)
            draw.bitmap((0,0), self.watermark, fill=None)
            path = self.storage_path + "/moa/" + filename
            depth_img.save(path, format="JPEG")
            path = self.storage_path + "/moa/latest.jpg"
            depth_img.save(path, format="JPEG")
            logger.info("Stored image: {}".format(path))

        self.count += 1
        if self.t1 - self.lastprint > 5:
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

        self.lasttime = self.t1

        return result_wrapper

    def process_image(self, image):
        self.t0 = time.time()
        np_data = np.fromstring(image, dtype=np.uint8)
        img = cv2.imdecode(np_data, cv2.IMREAD_COLOR)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        _,_,_ = self.inference(img)
        self.t1 = time.time()
        return actuation_vector, depth_img

    def inference(self, img):
        """Allow timing engine to override this"""
        return actuation_vector, full_depth_map
