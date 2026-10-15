import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import cv2
import numpy as np
import openscout_object_engine as engine_module
import pytest
import supervision as sv
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
    gimbal_info = None  # no gimbal attached to this frame

    result = engine.process_results(
        image_np, detections, vehicle_id, position_info, gimbal_info
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
    gimbal_info = None

    result = engine.process_results(
        image_np, detections, vehicle_id, position_info, gimbal_info
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


def _frame_input(producer, frame):
    """A Gabriel input carrying an EncodedFrame from producer."""
    return SimpleNamespace(
        id=SimpleNamespace(producer=producer),
        payload_type=engine_module.FRAME_TYPE,
        data=frame.SerializeToString(),
    )


def _engine_for_handle(predicted):
    """An engine whose detector predicts `predicted`, ready for handle()."""
    engine = _make_engine()
    engine.detector = MagicMock()
    engine.detector.predict.return_value = predicted
    engine.count = 0
    engine.lastcount = 0
    now = time.time()
    engine.t0 = now
    engine.t1 = now
    engine.lasttime = now
    engine.lastprint = now  # keep (t1 - lastprint) small so stats aren't printed
    return engine


def _jpeg_frame():
    frame = telemetry.EncodedFrame()
    frame.encoded_data = cv2.imencode(".jpg", np.zeros((100, 200, 3), dtype=np.uint8))[
        1
    ].tobytes()
    frame.position_info.global_position.latitude = 40.0
    frame.position_info.global_position.longitude = -79.0
    return frame


def test_handle_returns_an_empty_result_on_zero_detections():
    """Regression test: handle() used to guard process_results() behind
    `if len(results) > 0`, back when `results` was a length-1 ultralytics
    list. Now that process_image()/inference() return sv.Detections (whose
    len() is the detection count, 0 on a no-detections frame), that guard
    skipped process_results() entirely, leaving `detections` unbound and
    crashing with NameError. This drives handle() end to end with a frame
    that yields zero detections, to make sure it returns cleanly.
    """
    empty_detections = sv.Detections.empty()
    empty_detections.data["class_name"] = np.array([], dtype=object)
    engine = _engine_for_handle(empty_detections)

    result = engine.handle(_frame_input("drone1.frames", _jpeg_frame()))

    detection_result = result_pb2.DetectionResult()
    detection_result.ParseFromString(result)
    assert len(detection_result.detections) == 0


def test_handle_returns_detections_for_the_producers_vehicle():
    detections = sv.Detections(
        xyxy=np.array([[20.0, 10.0, 60.0, 50.0]], dtype=np.float32),
        confidence=np.array([0.87], dtype=np.float32),
        class_id=np.array([0]),
    )
    detections.data["class_name"] = np.array(["person"], dtype=object)
    engine = _engine_for_handle(detections)
    frame = _jpeg_frame()
    frame.gimbal_info.pose_body.pitch = -90.0

    result = engine.handle(_frame_input("drone1.frames", frame))

    detection_result = result_pb2.DetectionResult()
    detection_result.ParseFromString(result)
    [detection] = detection_result.detections
    assert detection.class_name == "person"
    assert detection.score == pytest.approx(87, rel=1e-4)
    assert detection.bbox.x_min == pytest.approx(0.10)
    assert detection.bbox.y_max == pytest.approx(0.50)
    engine.r.hset.assert_not_called()  # unittest mode stores nothing


@pytest.mark.parametrize(
    "producer, payload_type",
    [
        ("frames", engine_module.FRAME_TYPE),  # names no vehicle
        ("drone1.telemetry", "steeleagle_protocol.v1.messages.telemetry.Telemetry"),
    ],
)
def test_handle_ignores_inputs_it_cannot_read(producer, payload_type):
    engine = _engine_for_handle(sv.Detections.empty())
    engine_input = _frame_input(producer, _jpeg_frame())
    engine_input.payload_type = payload_type

    assert engine.handle(engine_input) is None
    engine.detector.predict.assert_not_called()
