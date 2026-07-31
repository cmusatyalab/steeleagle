import time
from unittest.mock import MagicMock

import cv2
import numpy as np
import openscout_object_engine as engine_module
import pytest
import supervision as sv
from gabriel_protocol import gabriel_pb2
from gabriel_server import cognitive_engine
from google.protobuf.any_pb2 import Any
from steeleagle_protocol.v1 import common_pb2
from steeleagle_protocol.v1.messages.result import result_pb2
from steeleagle_protocol.v1.messages.telemetry import telemetry_pb2 as telemetry


def _make_engine():
    engine = engine_module.OpenScoutObjectEngine.__new__(
        engine_module.OpenScoutObjectEngine
    )
    engine.threshold = 0.5
    engine.exclusions = None
    engine.geofence_enabled = False
    engine.geofence = []
    engine.unittest = True
    engine.store_detections = False
    engine.search_radius = 5.0
    engine.ttl_secs = 999_999
    engine.last_geodb_gc_time = time.time()
    engine.r = MagicMock()
    engine.r.geosearch.return_value = []
    return engine


def test_process_results_normalizes_absolute_pixel_boxes_to_fractional():
    engine = _make_engine()

    image_np = np.zeros((100, 200, 3), dtype=np.uint8)  # height=100, width=200
    detections = sv.Detections(
        xyxy=np.array([[20.0, 10.0, 60.0, 50.0]], dtype=np.float32),
        confidence=np.array([0.87], dtype=np.float32),
        class_id=np.array([0]),
    )
    detections.data["class_name"] = np.array(["person"], dtype=object)

    vehicle_id = "drone1"
    position_info = telemetry.PositionInfo()
    position_info.global_position.latitude = 40.0
    position_info.global_position.longitude = -79.0
    gimbal_status = telemetry.GimbalStatus()  # no pose_body set -> no gimbal attached

    result = engine.process_results(
        image_np, detections, vehicle_id, position_info, gimbal_status
    )

    assert result is not None
    assert len(result) == 1
    d = result[0]
    assert d["class"] == "person"
    assert d["score"] == pytest.approx(0.87, rel=1e-4)
    assert d["box"] == pytest.approx([0.10, 0.10, 0.50, 0.30])  # [y1,x1,y2,x2] / [h,w]
    assert all(isinstance(v, float) for v in d["box"])
    assert d["lat"] == 40.0
    assert d["lon"] == -79.0


def test_process_results_filters_excluded_classes():
    engine = _make_engine()
    engine.exclusions = [3]

    image_np = np.zeros((100, 200, 3), dtype=np.uint8)
    detections = sv.Detections(
        xyxy=np.array([[20.0, 10.0, 60.0, 50.0]], dtype=np.float32),
        confidence=np.array([0.87], dtype=np.float32),
        class_id=np.array([3]),
    )
    detections.data["class_name"] = np.array(["car"], dtype=object)

    vehicle_id = "drone1"
    position_info = telemetry.PositionInfo()
    gimbal_status = telemetry.GimbalStatus()

    result = engine.process_results(
        image_np, detections, vehicle_id, position_info, gimbal_status
    )

    assert result is None


def test_annotate_detections_returns_array_same_shape():
    image_np = np.zeros((50, 50, 3), dtype=np.uint8)
    detections = sv.Detections(
        xyxy=np.array([[5.0, 5.0, 20.0, 20.0]], dtype=np.float32),
        confidence=np.array([0.9], dtype=np.float32),
        class_id=np.array([0]),
    )
    detections.data["class_name"] = np.array(["person"], dtype=object)

    annotated = engine_module.annotate_detections(image_np, detections)

    assert annotated.shape == image_np.shape
    assert annotated.dtype == image_np.dtype


def test_handle_does_not_raise_on_zero_detections():
    """Regression test: handle() used to guard process_results() behind
    `if len(results) > 0`, back when `results` was a length-1 ultralytics
    list. Now that process_image()/inference() return sv.Detections (whose
    len() is the detection count, 0 on a no-detections frame), that guard
    skipped process_results() entirely, leaving `detections` unbound and
    crashing with NameError on `if detections is not None`. This drives the
    real handle() entry point end-to-end (not just process_results()) with a
    frame that yields zero detections, to make sure it returns cleanly.
    """
    engine = _make_engine()

    # Extra attributes handle() touches beyond what _make_engine() sets up.
    empty_detections = sv.Detections.empty()
    empty_detections.data["class_name"] = np.array([], dtype=object)
    engine.detector = MagicMock()
    engine.detector.predict.return_value = empty_detections
    engine.count = 0
    engine.lastcount = 0
    now = time.time()
    engine.t0 = now
    engine.t1 = now
    engine.lasttime = now
    engine.lastprint = now  # keep (t1 - lastprint) small so stats aren't printed

    # Build a real image the way a real caller would, so process_image()'s
    # cv2.imdecode() has something valid to decode.
    image_bytes = cv2.imencode(".jpg", np.zeros((10, 10, 3), dtype=np.uint8))[
        1
    ].tobytes()

    frame = telemetry.EncodedFrame()
    frame.encoded_data = image_bytes
    frame.position_info.global_position.latitude = 40.0
    frame.position_info.global_position.longitude = -79.0
    # gimbal_status left at default (no pose_body -> no gimbal attached)

    input_frame = gabriel_pb2.InputFrame()
    input_frame.payload_type = gabriel_pb2.PayloadType.IMAGE
    input_frame.any_payload.Pack(frame)

    vehicle_info = common_pb2.VehicleInfo(vehicle_id="drone1")
    client_info = Any()
    client_info.Pack(vehicle_info)

    result = engine.handle(input_frame, client_info)

    assert isinstance(result, cognitive_engine.Result)
    assert result.payload is not None

    assert result.payload.Is(result_pb2.ComputeResult.DESCRIPTOR)
    compute_result = result_pb2.ComputeResult()
    result.payload.Unpack(compute_result)

    assert len(compute_result.detection_result.detections) == 0
