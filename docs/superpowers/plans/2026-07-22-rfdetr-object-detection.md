# RF-DETR Object Detection Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add RF-DETR as a second, selectable object-detection backend in `backend/server/engines/detection/`, alongside the existing YOLO backend, while every downstream consumer (geofence filtering, Redis storage, protobuf serialization, stored-image annotation) stays backend-agnostic.

**Architecture:** A new `predictors.py` module normalizes both backends into `supervision.Detections` (RF-DETR returns this natively; ultralytics results convert via `sv.Detections.from_ultralytics`). `openscout_object_engine.py` is updated to load a `Predictor` through a `load_predictor()` factory (dispatching on an optional sidecar JSON file next to each model's weights) and to consume `sv.Detections` directly in `process_results()`, replacing the current polars `to_df()` path.

**Tech Stack:** Python 3.11, `ultralytics` (YOLO), `rfdetr` 1.8.3 (`RFDETRBase`/`RFDETRNano`/`RFDETRSmall`/`RFDETRMedium`/`RFDETRLarge`), `supervision` 0.29.1, `uv`, `pytest`.

## Global Constraints

- Local-weights loading only — no networked model registry (Roboflow's `inference` package is explicitly out of scope).
- A model name with no sidecar JSON file must default to today's YOLO behavior (`model/<name>.pt`) with zero migration for existing model directories.
- Runtime model swapping (`load_model(model_name)`) must keep working for both backends, and must never crash the engine — a failed swap logs an error and keeps the previously loaded model active.
- No changes to `result_pb2` (wire format) or the Redis schema (`store_detection_db`, `store_latest_drone_detection_db`, `geofilter_passed`).
- RF-DETR's `predict()` requires RGB input; the engine's frames are decoded as BGR (`cv2.imdecode`) and never converted for YOLO today — `RfDetrPredictor` must do its own BGR→RGB conversion; `YoloPredictor` must not change this existing behavior.
- Spec reference: `docs/superpowers/specs/2026-07-22-rfdetr-object-detection-design.md`.

---

## Task 1: Add dependencies and test tooling

**Files:**
- Modify: `backend/server/engines/detection/pyproject.toml`

**Interfaces:**
- Produces: `rfdetr`, `supervision`, and `pytest` (dev) become importable inside the project's `.venv` for all later tasks.

- [ ] **Step 1: Add `rfdetr` and `supervision` to dependencies, and a `pytest` dev dependency group**

Open `backend/server/engines/detection/pyproject.toml`. Replace:

```toml
dependencies = [
   "redis",
   "opencv-python-headless",
   "numpy",
   "pykml",
   "pygeodesy",
   "ultralytics==8.4.66",
   "scipy",
   "Pillow",
   "gabriel-server>=4.1.2",
   "steeleagle-sdk>=1.0.16",
   "torch"
]
```

with:

```toml
dependencies = [
   "redis",
   "opencv-python-headless",
   "numpy",
   "pykml",
   "pygeodesy",
   "ultralytics==8.4.66",
   "rfdetr>=1.8.3",
   "supervision>=0.29.1",
   "scipy",
   "Pillow",
   "gabriel-server>=4.1.2",
   "steeleagle-sdk>=1.0.16",
   "torch"
]

[dependency-groups]
dev = [
   "pytest>=8.4.2",
]
```

- [ ] **Step 2: Sync the environment**

Run:

```bash
cd backend/server/engines/detection && uv sync
```

Expected: completes without error (this will download `rfdetr`, `supervision`, and their transitive dependencies — may take a few minutes on first run).

- [ ] **Step 3: Verify the new dependencies import**

Run:

```bash
cd backend/server/engines/detection && uv run python -c "import rfdetr, supervision, pytest; print('deps ok')"
```

Expected: prints `deps ok` with no errors.

- [ ] **Step 4: Commit**

```bash
cd backend/server/engines/detection
git add pyproject.toml uv.lock
git commit -m "Add rfdetr, supervision, and pytest dependencies to detection engine"
```

---

## Task 2: `predictors.py` — base interface and `YoloPredictor`

**Files:**
- Create: `backend/server/engines/detection/predictors.py`
- Create: `backend/server/engines/detection/tests/__init__.py`
- Create: `backend/server/engines/detection/tests/test_predictors.py`

**Interfaces:**
- Produces: `predictors.Predictor` (base class, documents the `predict(image_np) -> sv.Detections` contract), `predictors.YoloPredictor(weights_path: str, threshold: float)` with `.predict(image_np: np.ndarray) -> sv.Detections`.

- [ ] **Step 1: Create the empty tests package**

Create `backend/server/engines/detection/tests/__init__.py` with empty content.

- [ ] **Step 2: Write the failing test for `YoloPredictor`**

Create `backend/server/engines/detection/tests/test_predictors.py`:

```python
import numpy as np

import predictors


def test_yolo_predictor_predict_wires_model_and_conversion(monkeypatch):
    fake_results = object()

    class FakeYoloModel:
        def __init__(self):
            self.received = None

        def predict(self, image, conf, verbose):
            self.received = (image, conf, verbose)
            return [fake_results]

    fake_model = FakeYoloModel()
    monkeypatch.setattr(predictors, "YOLO", lambda path: fake_model)

    sentinel = object()

    def fake_from_ultralytics(cls, results):
        assert results is fake_results
        return sentinel

    monkeypatch.setattr(
        predictors.sv.Detections,
        "from_ultralytics",
        classmethod(fake_from_ultralytics),
    )

    predictor = predictors.YoloPredictor("model/coco.pt", threshold=0.4)
    image = np.zeros((2, 2, 3), dtype=np.uint8)

    result = predictor.predict(image)

    assert result is sentinel
    received_image, conf, verbose = fake_model.received
    assert np.array_equal(received_image, image)
    assert conf == 0.4
    assert verbose is False
```

- [ ] **Step 3: Run the test to verify it fails**

Run:

```bash
cd backend/server/engines/detection && uv run pytest tests/test_predictors.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'predictors'` (the module doesn't exist yet).

- [ ] **Step 4: Create `predictors.py` with the base class and `YoloPredictor`**

Create `backend/server/engines/detection/predictors.py`:

```python
import numpy as np
import supervision as sv
from ultralytics import YOLO


class Predictor:
    """Common interface for a detection backend.

    predict(image_np) takes a BGR numpy image (as decoded by cv2.imdecode)
    and returns a supervision.Detections with .xyxy in absolute pixel
    coordinates (relative to image_np) and .data["class_name"] populated.
    """

    def predict(self, image_np: np.ndarray) -> sv.Detections:
        raise NotImplementedError


class YoloPredictor(Predictor):
    def __init__(self, weights_path: str, threshold: float):
        self.model = YOLO(weights_path)
        self.threshold = threshold

    def predict(self, image_np: np.ndarray) -> sv.Detections:
        results = self.model.predict(image_np, conf=self.threshold, verbose=False)
        return sv.Detections.from_ultralytics(results[0])
```

- [ ] **Step 5: Run the test to verify it passes**

Run:

```bash
cd backend/server/engines/detection && uv run pytest tests/test_predictors.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd backend/server/engines/detection
git add predictors.py tests/__init__.py tests/test_predictors.py
git commit -m "Add Predictor base interface and YoloPredictor backend"
```

---

## Task 3: `predictors.py` — `RfDetrPredictor`

**Files:**
- Modify: `backend/server/engines/detection/predictors.py`
- Modify: `backend/server/engines/detection/tests/test_predictors.py`

**Interfaces:**
- Consumes: `predictors.Predictor` from Task 2.
- Produces: `predictors.RfDetrPredictor(weights_path: str, threshold: float, variant: str, classes: list[str] | None = None)` with `.predict(image_np: np.ndarray) -> sv.Detections`. `predictors._RFDETR_VARIANTS: dict[str, type]` mapping variant name to the `RFDETR*` class, used by Task 4's factory.

- [ ] **Step 1: Write the failing tests for `RfDetrPredictor`**

Append to `backend/server/engines/detection/tests/test_predictors.py`:

```python
import supervision as sv


def _fake_rfdetr_detections(class_id, class_name):
    detections = sv.Detections(
        xyxy=np.array([[0.0, 0.0, 1.0, 1.0]], dtype=np.float32),
        confidence=np.array([0.9], dtype=np.float32),
        class_id=np.array([class_id]),
    )
    detections.data["class_name"] = np.array([class_name], dtype=object)
    return detections


def test_rfdetr_predictor_converts_bgr_to_rgb_and_passes_threshold(monkeypatch):
    class FakeRfDetrModel:
        def __init__(self):
            self.received = None

        def predict(self, image, threshold):
            self.received = (image, threshold)
            return _fake_rfdetr_detections(class_id=0, class_name="dog")

    fake_model = FakeRfDetrModel()
    monkeypatch.setattr(
        predictors, "_RFDETR_VARIANTS", {"base": lambda pretrain_weights: fake_model}
    )

    predictor = predictors.RfDetrPredictor("model/x.pth", threshold=0.6, variant="base")
    bgr_image = np.zeros((2, 2, 3), dtype=np.uint8)
    bgr_image[0, 0] = [255, 0, 0]  # blue pixel in BGR order

    result = predictor.predict(bgr_image)

    received_image, threshold = fake_model.received
    assert threshold == 0.6
    assert received_image[0, 0].tolist() == [0, 0, 255]  # converted to RGB (red)
    assert result.data["class_name"].tolist() == ["dog"]


def test_rfdetr_predictor_applies_classes_override(monkeypatch):
    class FakeRfDetrModel:
        def predict(self, image, threshold):
            return _fake_rfdetr_detections(class_id=1, class_name="wrong-name")

    monkeypatch.setattr(
        predictors,
        "_RFDETR_VARIANTS",
        {"base": lambda pretrain_weights: FakeRfDetrModel()},
    )

    predictor = predictors.RfDetrPredictor(
        "model/x.pth", threshold=0.5, variant="base", classes=["cat", "dog"]
    )

    result = predictor.predict(np.zeros((2, 2, 3), dtype=np.uint8))

    assert result.data["class_name"].tolist() == ["dog"]  # class_id=1 -> classes[1]


def test_rfdetr_predictor_without_classes_keeps_model_provided_names(monkeypatch):
    class FakeRfDetrModel:
        def predict(self, image, threshold):
            return _fake_rfdetr_detections(class_id=0, class_name="person")

    monkeypatch.setattr(
        predictors,
        "_RFDETR_VARIANTS",
        {"base": lambda pretrain_weights: FakeRfDetrModel()},
    )

    predictor = predictors.RfDetrPredictor("model/x.pth", threshold=0.5, variant="base")

    result = predictor.predict(np.zeros((2, 2, 3), dtype=np.uint8))

    assert result.data["class_name"].tolist() == ["person"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
cd backend/server/engines/detection && uv run pytest tests/test_predictors.py -v
```

Expected: the three new tests FAIL with `AttributeError: module 'predictors' has no attribute 'RfDetrPredictor'` (and `_RFDETR_VARIANTS` missing). The Task 2 test still passes.

- [ ] **Step 3: Add `RfDetrPredictor` to `predictors.py`**

In `backend/server/engines/detection/predictors.py`, replace:

```python
import numpy as np
import supervision as sv
from ultralytics import YOLO
```

with:

```python
import cv2
import numpy as np
import supervision as sv
from rfdetr import RFDETRBase, RFDETRLarge, RFDETRMedium, RFDETRNano, RFDETRSmall
from ultralytics import YOLO

# RFDETRBase is deprecated as of rfdetr 1.7.0 (still functional; scheduled
# for removal in 2.0.0) but remains a valid variant choice until then.
_RFDETR_VARIANTS = {
    "base": RFDETRBase,
    "large": RFDETRLarge,
    "nano": RFDETRNano,
    "small": RFDETRSmall,
    "medium": RFDETRMedium,
}
```

Then append to the end of the file:

```python
class RfDetrPredictor(Predictor):
    def __init__(
        self,
        weights_path: str,
        threshold: float,
        variant: str,
        classes: list[str] | None = None,
    ):
        model_cls = _RFDETR_VARIANTS[variant]
        self.model = model_cls(pretrain_weights=weights_path)
        self.threshold = threshold
        self.classes = classes

    def predict(self, image_np: np.ndarray) -> sv.Detections:
        rgb = cv2.cvtColor(image_np, cv2.COLOR_BGR2RGB)
        detections = self.model.predict(rgb, threshold=self.threshold)
        if self.classes is not None:
            detections.data["class_name"] = np.array(
                [self.classes[i] for i in detections.class_id], dtype=object
            )
        return detections
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
cd backend/server/engines/detection && uv run pytest tests/test_predictors.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
cd backend/server/engines/detection
git add predictors.py tests/test_predictors.py
git commit -m "Add RfDetrPredictor backend with RGB conversion and class-name override"
```

---

## Task 4: `predictors.py` — `load_predictor()` factory

**Files:**
- Modify: `backend/server/engines/detection/predictors.py`
- Modify: `backend/server/engines/detection/tests/test_predictors.py`

**Interfaces:**
- Consumes: `predictors.YoloPredictor`, `predictors.RfDetrPredictor`, `predictors._RFDETR_VARIANTS` from Tasks 2–3.
- Produces: `predictors.UnknownModelArchError(Exception)`. `predictors.load_predictor(model_name: str, threshold: float, model_dir: str = "model") -> Predictor` — the factory `openscout_object_engine.py` (Task 5) will call. Raises `FileNotFoundError` for missing weights and `UnknownModelArchError` for a malformed/unknown sidecar `arch`.

- [ ] **Step 1: Write the failing tests for `load_predictor`**

Append to `backend/server/engines/detection/tests/test_predictors.py`:

```python
import json

import pytest


def test_load_predictor_defaults_to_yolo_without_sidecar(tmp_path, monkeypatch):
    (tmp_path / "coco.pt").write_bytes(b"")
    captured = {}
    monkeypatch.setattr(
        predictors,
        "YOLO",
        lambda path: captured.setdefault("path", path) or object(),
    )

    predictor = predictors.load_predictor("coco", 0.5, model_dir=str(tmp_path))

    assert isinstance(predictor, predictors.YoloPredictor)
    assert captured["path"] == str(tmp_path / "coco.pt")


def test_load_predictor_missing_yolo_weights_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        predictors.load_predictor("coco", 0.5, model_dir=str(tmp_path))


def test_load_predictor_rfdetr_with_sidecar(tmp_path, monkeypatch):
    (tmp_path / "myrfdetr.pth").write_bytes(b"")
    (tmp_path / "myrfdetr.json").write_text(
        json.dumps({"arch": "rfdetr", "variant": "base", "classes": ["a", "b"]})
    )
    monkeypatch.setattr(
        predictors, "_RFDETR_VARIANTS", {"base": lambda pretrain_weights: object()}
    )

    predictor = predictors.load_predictor("myrfdetr", 0.5, model_dir=str(tmp_path))

    assert isinstance(predictor, predictors.RfDetrPredictor)
    assert predictor.classes == ["a", "b"]


def test_load_predictor_rfdetr_missing_variant_raises(tmp_path):
    (tmp_path / "myrfdetr.pth").write_bytes(b"")
    (tmp_path / "myrfdetr.json").write_text(json.dumps({"arch": "rfdetr"}))

    with pytest.raises(predictors.UnknownModelArchError):
        predictors.load_predictor("myrfdetr", 0.5, model_dir=str(tmp_path))


def test_load_predictor_rfdetr_missing_weights_raises(tmp_path):
    (tmp_path / "myrfdetr.json").write_text(
        json.dumps({"arch": "rfdetr", "variant": "base"})
    )

    with pytest.raises(FileNotFoundError):
        predictors.load_predictor("myrfdetr", 0.5, model_dir=str(tmp_path))


def test_load_predictor_unknown_arch_raises(tmp_path):
    (tmp_path / "weird.json").write_text(json.dumps({"arch": "bogus"}))

    with pytest.raises(predictors.UnknownModelArchError):
        predictors.load_predictor("weird", 0.5, model_dir=str(tmp_path))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
cd backend/server/engines/detection && uv run pytest tests/test_predictors.py -v
```

Expected: the six new tests FAIL with `AttributeError: module 'predictors' has no attribute 'load_predictor'` (and `UnknownModelArchError` missing). Earlier tests still pass.

- [ ] **Step 3: Add `UnknownModelArchError` and `load_predictor` to `predictors.py`**

In `backend/server/engines/detection/predictors.py`, replace the top import block:

```python
import cv2
import numpy as np
import supervision as sv
from rfdetr import RFDETRBase, RFDETRLarge, RFDETRMedium, RFDETRNano, RFDETRSmall
from ultralytics import YOLO
```

with:

```python
import json
import os

import cv2
import numpy as np
import supervision as sv
from rfdetr import RFDETRBase, RFDETRLarge, RFDETRMedium, RFDETRNano, RFDETRSmall
from ultralytics import YOLO
```

Then append to the end of the file:

```python
class UnknownModelArchError(Exception):
    pass


def load_predictor(model_name: str, threshold: float, model_dir: str = "model") -> Predictor:
    sidecar_path = os.path.join(model_dir, f"{model_name}.json")
    meta = {"arch": "yolo"}
    if os.path.exists(sidecar_path):
        with open(sidecar_path) as f:
            meta = json.load(f)

    arch = meta.get("arch", "yolo")

    if arch == "yolo":
        weights_path = os.path.join(model_dir, f"{model_name}.pt")
        if not os.path.exists(weights_path):
            raise FileNotFoundError(weights_path)
        return YoloPredictor(weights_path, threshold)

    if arch == "rfdetr":
        variant = meta.get("variant")
        if variant not in _RFDETR_VARIANTS:
            raise UnknownModelArchError(
                f"Unknown or missing RF-DETR variant: {variant!r}"
            )
        weights_path = os.path.join(model_dir, f"{model_name}.pth")
        if not os.path.exists(weights_path):
            raise FileNotFoundError(weights_path)
        return RfDetrPredictor(
            weights_path, threshold, variant=variant, classes=meta.get("classes")
        )

    raise UnknownModelArchError(f"Unknown model arch: {arch!r}")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
cd backend/server/engines/detection && uv run pytest tests/test_predictors.py -v
```

Expected: all tests PASS (12 total across Tasks 2–4).

- [ ] **Step 5: Commit**

```bash
cd backend/server/engines/detection
git add predictors.py tests/test_predictors.py
git commit -m "Add load_predictor factory with sidecar-JSON backend dispatch"
```

---

## Task 5: Wire `openscout_object_engine.py` to the new predictor backends

**Files:**
- Modify: `backend/server/engines/detection/openscout_object_engine.py`
- Create: `backend/server/engines/detection/tests/test_engine.py`

**Interfaces:**
- Consumes: `predictors.load_predictor`, `predictors.UnknownModelArchError` from Task 4.
- Produces: `openscout_object_engine.annotate_detections(image_bgr: np.ndarray, detections: sv.Detections) -> np.ndarray` (module-level helper, backend-agnostic).

- [ ] **Step 1: Write the failing tests for the new engine behavior**

Create `backend/server/engines/detection/tests/test_engine.py`:

```python
import time
from unittest.mock import MagicMock

import numpy as np
import pytest
import supervision as sv
from steeleagle_sdk.protocol.messages import telemetry_pb2 as telemetry

import openscout_object_engine as engine_module


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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
cd backend/server/engines/detection && uv run pytest tests/test_engine.py -v
```

Expected: FAIL — `process_results` still calls `sv_detections[0].to_df(...)` on the plain `sv.Detections` object passed in (`AttributeError`), and `annotate_detections` doesn't exist yet (`AttributeError: module 'openscout_object_engine' has no attribute 'annotate_detections'`).

- [ ] **Step 3: Update imports**

In `backend/server/engines/detection/openscout_object_engine.py`, replace:

```python
import cv2
import numpy as np
import redis
from gabriel_protocol import gabriel_pb2
from gabriel_server import cognitive_engine, local_engine
from google.protobuf.any_pb2 import Any
from PIL import Image
from pygeodesy.sphericalNvector import LatLon
from pykml import parser
from scipy.spatial.transform import Rotation as R
from steeleagle_sdk.protocol.messages import result_pb2
from steeleagle_sdk.protocol.messages import telemetry_pb2 as telemetry
from ultralytics import YOLO
```

with:

```python
import cv2
import numpy as np
import redis
import supervision as sv
from gabriel_protocol import gabriel_pb2
from gabriel_server import cognitive_engine, local_engine
from google.protobuf.any_pb2 import Any
from PIL import Image
from pygeodesy.sphericalNvector import LatLon
from pykml import parser
from scipy.spatial.transform import Rotation as R
from steeleagle_sdk.protocol.messages import result_pb2
from steeleagle_sdk.protocol.messages import telemetry_pb2 as telemetry

from predictors import UnknownModelArchError, load_predictor
```

- [ ] **Step 4: Replace `PytorchPredictor` with `annotate_detections`**

Replace:

```python
class PytorchPredictor:
    def __init__(self, model, threshold):
        model_path = os.path.join("model", f"{model}.pt")
        logger.info(f"Loading new model {model} at {model_path}...")
        self.detection_model = self.load_model(model_path)
        self.detection_model.conf = threshold
        self.output_dict = None

    def load_model(self, model_path):
        # Load model
        model = YOLO(model_path)
        return model

    def infer(self, image):
        return self.model(image)
```

with:

```python
def annotate_detections(image_bgr, detections):
    labels = [
        f"{name} {confidence:.2f}"
        for name, confidence in zip(
            detections.data["class_name"], detections.confidence
        )
    ]
    annotated = sv.BoxAnnotator().annotate(image_bgr.copy(), detections)
    return sv.LabelAnnotator().annotate(annotated, detections, labels=labels)
```

- [ ] **Step 5: Update `__init__` to use `load_predictor`**

Replace:

```python
        self.detector = PytorchPredictor(args.model, args.threshold)
```

with:

```python
        self.detector = load_predictor(args.model, args.threshold)
```

- [ ] **Step 6: Update `load_model` to use `load_predictor` and fail gracefully**

Replace:

```python
    def load_model(self, model_name):
        path = "./model/" + model_name + ".pt"
        if not os.path.exists(path):
            logger.error(f"Model {path} not found. Sticking with previous model.")
        else:
            self.detector = PytorchPredictor(model_name, self.threshold)
            self.model = model_name
```

with:

```python
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
```

- [ ] **Step 7: Update `inference` to call the predictor directly**

Replace:

```python
    def inference(self, img):
        """Allow timing engine to override this"""
        return self.detector.detection_model.predict(
            img, conf=self.threshold, verbose=False
        )
```

with:

```python
    def inference(self, img):
        """Allow timing engine to override this"""
        return self.detector.predict(img)
```

- [ ] **Step 8: Rewrite `process_results` to consume `sv.Detections`**

Replace the entire `process_results` method:

```python
    def process_results(
        self, image_np, results, vehicle_info, position_info, gimbal_info
    ):
        df = results[0].to_df(normalize=True)  # polars dataframe

        exclusions = self.exclusions or []
        if not df.is_empty():
            df = df.filter(
                df["confidence"] > self.threshold, ~df["class"].is_in(exclusions)
            )

        detections = []
        timestamp_millis = int(time.time() * 1000)
        filename = str(timestamp_millis) + ".jpg"
        if self.store_detections:
            detection_url = os.path.join(
                os.environ["WEBSERVER"],
                "detected",
                "vehicles",
                vehicle_info.name,
                filename,
            )
        else:
            detection_url = ""

        run_hsv_filter = False

        for row in df.iter_rows(named=True):
            logger.info(row)
            logger.info(f"Detected : {row['name']} - Score: {row['confidence']:.3f}")
            box = row["box"]
            box = [box["y1"], box["x1"], box["y2"], box["x2"]]
            global_pos = position_info.global_position
            if gimbal_info.num_gimbals == 0:
                logger.warning(
                    "Number of gimbals is zero, using the vehicle global location for target coordinates"
                )
                lon = global_pos.longitude
                lat = global_pos.latitude
                p = LatLon(lat, lon)
            else:
                target_pitch, target_yaw = self.calculate_target_pitch_yaw(
                    box, image_np, position_info, gimbal_info
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
                "id": vehicle_info.name,
                "class": row["name"],
                "score": row["confidence"],
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
            # self.store_hsv_image(image_np, cpt_config, vehicle_info.name)

        # Store detection image
        if self.store_detections and not df.is_empty() and not self.unittest:
            try:
                im_bgr = results[0].plot()
                self.store_detections_disk(
                    im_bgr, filename, vehicle_info.name, df["name"].unique().to_list()
                )
            except IndexError:
                logger.error(
                    f"IndexError while getting bounding boxes [{traceback.format_exc()}]"
                )

        now_secs = time.time()
        if now_secs - self.last_geodb_gc_time >= self.ttl_secs:
            self.geodb_garbage_collection()
            self.last_geodb_gc_time = now_secs

        return detections if not df.is_empty() else None
```

with:

```python
    def process_results(
        self, image_np, sv_detections, vehicle_info, position_info, gimbal_info
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
                vehicle_info.name,
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
            if gimbal_info.num_gimbals == 0:
                logger.warning(
                    "Number of gimbals is zero, using the vehicle global location for target coordinates"
                )
                lon = global_pos.longitude
                lat = global_pos.latitude
                p = LatLon(lat, lon)
            else:
                target_pitch, target_yaw = self.calculate_target_pitch_yaw(
                    box, image_np, position_info, gimbal_info
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
                "id": vehicle_info.name,
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
            # self.store_hsv_image(image_np, cpt_config, vehicle_info.name)

        # Store detection image
        if self.store_detections and len(sv_detections) > 0 and not self.unittest:
            try:
                annotated = annotate_detections(image_np, sv_detections)
                self.store_detections_disk(
                    annotated,
                    filename,
                    vehicle_info.name,
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
```

- [ ] **Step 9: Run the tests to verify they pass**

Run:

```bash
cd backend/server/engines/detection && uv run pytest tests/ -v
```

Expected: all tests PASS (Tasks 2–5 combined).

- [ ] **Step 10: Sanity-check the module still imports cleanly standalone**

Run:

```bash
cd backend/server/engines/detection && uv run python -c "import openscout_object_engine; print('import ok')"
```

Expected: prints `import ok` with no errors.

- [ ] **Step 11: Commit**

```bash
cd backend/server/engines/detection
git add openscout_object_engine.py tests/test_engine.py
git commit -m "Wire OpenScoutObjectEngine to backend-agnostic Predictor interface"
```

---

## Self-Review Notes

- **Spec coverage:** sidecar resolution + backward-compat default (Task 4), RF-DETR loading via direct local weights (Task 3), runtime model swap with graceful failure (Task 5 Step 6), `sv.Detections` normalization for both backends (Tasks 2–3), `process_results`/stored-image annotation decoupled from architecture (Task 5 Steps 4 & 8), new dependencies (Task 1) — all covered.
- **Type consistency:** `load_predictor(model_name, threshold, model_dir="model")` signature matches every call site (Task 5 Steps 5–6 call it with two positional args, relying on the default `model_dir`; Task 4's tests pass `model_dir=` explicitly). `Predictor.predict(image_np) -> sv.Detections` is implemented identically by both subclasses and consumed identically in `inference()`.
- **No placeholders:** every step has complete, runnable code — no TODOs left for the implementer to fill in beyond the pre-existing `# TODO: need to get hsv bounds` comments, which are carried over verbatim from the current codebase (out of scope for this feature; not new placeholders introduced by this plan).
