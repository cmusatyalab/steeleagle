import cv2
from gabriel_server import cognitive_engine
from steeleagle_sdk.protocol.messages import telemetry_pb2 as telemetry
from gabriel_protocol import gabriel_pb2
from steeleagle_sdk.protocol.messages import result_pb2
from google.protobuf.any_pb2 import Any
import numpy as np
import logging
import redis
import json

logger = logging.getLogger(__name__)

class ArucoMarkerDetectorEngine(cognitive_engine.Engine):
    def __init__(self, args):
        self.r = redis.Redis(
            host=args.redis_host,
            port=args.redis,
            username="steeleagle",
            password=f"{args.auth}",
            decode_responses=True,
        )
        self.r.ping()
        logger.info(f"Connected to redis on port {args.redis}...")


    def store_latest_drone_detection_db(self, detections):
        vehicle_name = detections[0]["id"]
        key = f"aruco-detection:{vehicle_name}"

        pipe = self.r.pipeline()
        pipe.delete(key)
        pipe.rpush(key, *[json.dumps(d) for d in detections])
        pipe.pexpire(key, 100)

        pipe.execute()

    def handle(self, input_frame):
        if input_frame.payload_type != gabriel_pb2.PayloadType.IMAGE:
            status = gabriel_pb2.Status()
            status.code = gabriel_pb2.StatusCode.WRONG_INPUT_FORMAT
            status.message = "Ignoring non-image payload"
            return cognitive_engine.Result(status, None)

        frame = telemetry.Frame()
        assert input_frame.WhichOneof("payload") == "any_payload"
        assert input_frame.any_payload.Is(telemetry.Frame.DESCRIPTOR)
        input_frame.any_payload.Unpack(frame)

        np_data = np.frombuffer(frame.data, dtype=np.uint8)
        image = cv2.imdecode(np_data, cv2.IMREAD_COLOR)
        height, width = image.shape[:2]

        arucoDict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_ARUCO_ORIGINAL)
        arucoParams = cv2.aruco.DetectorParameters()
        detector = cv2.aruco.ArucoDetector(arucoDict, arucoParams)
        corners, ids, _ = detector.detectMarkers(image)

        compute_result = result_pb2.ComputeResult()
        detection_result = result_pb2.DetectionResult()

        detections = []
        vehicle_info = frame.vehicle_info

        for i, corner in enumerate(corners):
            det_object = result_pb2.Detection()
            det_object.detection_id = i
            det_object.class_name = f"aruco_{ids[i][0]}"
            c = corner[0]
            logger.info(f'{c=}')

            bbox = result_pb2.BoundingBox(
                x_min = np.min(c[:, 0]) / width,
                y_min = np.min(c[:, 1]) / height,
                x_max = np.max(c[:, 0]) / width,
                y_max = np.max(c[:, 1]) / height,
            )

            logger.info(f'{bbox=}')
            det_object.bbox.CopyFrom(bbox)
            detection_result.detections.append(det_object)
            box = [bbox.y_min, bbox.x_min, bbox.y_max, bbox.x_max]
            detection = {
                "id": vehicle_info.name,
                "box": box,
            }
            detections.append(detection)

        if len(detections) > 0:
            self.store_latest_drone_detection_db(detections)

        compute_result.detection_result.CopyFrom(detection_result)
        frame_result = result_pb2.FrameResult()
        frame_result.type = "aruco-tag-detection"
        frame_result.result.append(compute_result)
        frame_result.timestamp.GetCurrentTime()

        any_payload = Any()
        any_payload.Pack(frame_result)

        status = gabriel_pb2.Status()
        return cognitive_engine.Result(status, any_payload)
