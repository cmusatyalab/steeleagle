import json
import os

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
        weights_path: str | None,
        threshold: float,
        variant: str,
        classes: list[str] | None = None,
    ):
        model_cls = _RFDETR_VARIANTS[variant]
        # Omit pretrain_weights entirely (rather than passing None) when no
        # local checkpoint is given, so the variant class falls through to
        # its own default pretrained weights filename and auto-downloads it
        # to the rfdetr cache dir (~/.roboflow/models, or $RF_HOME). Passing
        # pretrain_weights=None explicitly would instead skip the download
        # and leave the model uninitialized.
        self.model = (
            model_cls(pretrain_weights=weights_path)
            if weights_path is not None
            else model_cls()
        )
        self.threshold = threshold
        self.classes = classes

    def predict(self, image_np: np.ndarray) -> sv.Detections:
        rgb = cv2.cvtColor(image_np, cv2.COLOR_BGR2RGB)
        detections = self.model.predict(rgb, threshold=self.threshold)
        if self.classes is not None:
            # class_id is not always a valid index into self.classes: rfdetr
            # reserves a "no-object"/background logit slot at index
            # len(model.class_names), and pretrained-COCO checkpoints use
            # sparse COCO category IDs (1-90, with gaps) rather than 0-based
            # indices. rfdetr's own predict() already resolves those cases
            # correctly in detections.data["class_name"], so fall back to
            # that name whenever class_id falls outside our override list.
            model_names = detections.data["class_name"]
            detections.data["class_name"] = np.array(
                [
                    self.classes[i] if 0 <= i < len(self.classes) else name
                    for i, name in zip(detections.class_id, model_names)
                ],
                dtype=object,
            )
        return detections


class UnknownModelArchError(Exception):
    pass


def load_predictor(
    model_name: str, threshold: float, model_dir: str = "model"
) -> Predictor:
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
        # A local .pth is only required for a custom-trained model. If it's
        # not there, assume the caller wants a stock pretrained variant and
        # let RfDetrPredictor auto-download it.
        weights_path = os.path.join(model_dir, f"{model_name}.pth")
        if not os.path.exists(weights_path):
            weights_path = None
        return RfDetrPredictor(
            weights_path, threshold, variant=variant, classes=meta.get("classes")
        )

    raise UnknownModelArchError(f"Unknown model arch: {arch!r}")
