import json

import numpy as np
import predictors
import pytest
import supervision as sv


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
