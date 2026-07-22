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
