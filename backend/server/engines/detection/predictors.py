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
