import time
from unittest.mock import MagicMock

import numpy as np
import openscout_object_engine as engine_module
import pytest
import supervision as sv
from steeleagle_sdk.protocol.messages import telemetry_pb2 as telemetry


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

    vehicle_info = telemetry.VehicleInfo(name="drone1")
    position_info = telemetry.PositionInfo()
    position_info.global_position.latitude = 40.0
    position_info.global_position.longitude = -79.0
    gimbal_info = telemetry.GimbalInfo()  # num_gimbals defaults to 0

    result = engine.process_results(
        image_np, detections, vehicle_info, position_info, gimbal_info
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

    vehicle_info = telemetry.VehicleInfo(name="drone1")
    position_info = telemetry.PositionInfo()
    gimbal_info = telemetry.GimbalInfo()

    result = engine.process_results(
        image_np, detections, vehicle_info, position_info, gimbal_info
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
