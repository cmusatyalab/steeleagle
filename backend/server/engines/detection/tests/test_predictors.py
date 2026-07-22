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
