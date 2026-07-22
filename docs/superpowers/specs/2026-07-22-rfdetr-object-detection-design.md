# RF-DETR Support in the Object Detection Engine

## Problem

`backend/server/engines/detection/openscout_object_engine.py` only supports
YOLO models via `ultralytics.YOLO`. Model loading (`PytorchPredictor`) and
result iteration (`results[0].to_df(normalize=True)`, a polars DataFrame) are
both tied directly to ultralytics' API. We want to add RF-DETR as a second
detection backend, selectable per model, while reusing the shared pipeline:
geofence filtering, duplicate-detection suppression, Redis storage
(`store_detection_db`, `store_latest_drone_detection_db`), protobuf
serialization (`result_pb2.Detection`/`BoundingBox`), and stored-image
annotation.

Models are loaded by name both at startup (`--model` CLI arg) and at runtime,
when a vehicle requests a model swap (handled today via `load_model()`,
following the same pattern as `obstacle_avoidance_engine.py`'s
`maybe_load_model()`). A model name resolves to a file under the mounted
`model/` directory (host `./models` → container `/steeleagle/model/`, per
`docker-compose.yml`). Whatever we build must support switching between a
YOLO model and an RF-DETR model at runtime, not just at process startup.

## Goals

- Add RF-DETR as a selectable detection backend, loaded from local weights
  under `model/` (no networked model registry — must work offline).
- Reuse 100% of the existing geofence / dedup / Redis / protobuf / stored-image
  pipeline unchanged; backend differences are fully contained in the
  model-loading and inference layer.
- Support runtime model swapping between YOLO and RF-DETR models, matching
  today's `load_model(model_name)` behavior (including graceful failure —
  keep the previous model loaded if the requested swap fails).
- Existing YOLO model directories keep working with zero migration.

## Non-goals

- A networked/managed model registry (e.g. Roboflow's `inference` package)
  — out of scope; local-weights loading only.
- Changing the wire format (`result_pb2`) or the Redis schema.
- Support for more than two backends in this pass (the design should make a
  third backend easy to add later, but we're not building one now).

## Architecture

```
openscout_object_engine.py
  __init__ / load_model()  --calls-->  load_predictor(model_name, threshold)
  inference()               --calls-->  predictor.predict(image_np) -> sv.Detections
  process_results()         --consumes--> sv.Detections (backend-agnostic)
  store_detections_disk()   --uses-->    shared sv.BoxAnnotator/LabelAnnotator helper

predictors.py (new)
  Predictor            - base class: predict(image_np) -> sv.Detections
  YoloPredictor         - wraps ultralytics.YOLO
  RfDetrPredictor       - wraps RFDETRBase/RFDETRLarge/... (rfdetr package)
  load_predictor()      - factory; reads sidecar JSON, picks + constructs backend
```

The key move is normalizing both backends into a single
`supervision.Detections` object (`.xyxy` absolute-pixel boxes, `.confidence`,
`.class_id`, and a `.data["class_name"]` array). RF-DETR's own
`model.predict()` already returns `sv.Detections` natively; ultralytics
results convert via `sv.Detections.from_ultralytics(results[0])`. Once both
backends hand back the same type, `process_results()` and the stored-image
annotation path never branch on architecture — they only know about
`sv.Detections`. `supervision` is already a transitive dependency of
`rfdetr`, so this adds no meaningful new dependency footprint, and lets us
drop the polars `to_df()` usage entirely.

## Model resolution & sidecar metadata

`load_predictor(model_name, threshold)` resolves weights the same way
`load_model()` does today, plus an optional sidecar JSON file:

- Look for `model/<model_name>.json`.
- **Not found → arch defaults to `yolo`, weights = `model/<model_name>.pt`.**
  This is exactly today's behavior, so every existing model directory keeps
  working with no migration step.
- Found, `"arch": "yolo"` → same as above; sidecar is optional for YOLO.
- Found, `"arch": "rfdetr"` → weights = `model/<model_name>.pth`, and the
  sidecar must also provide:
  - `"variant"`: one of `base`/`large`/`nano`/`small`/`medium`, mapping to
    the matching `RFDETR*` class (RF-DETR checkpoints are
    architecture-specific, unlike ultralytics' `YOLO()` which auto-detects
    architecture from the checkpoint itself).
  - `"classes"`: an ordered list of class names, index = `class_id`. RF-DETR
    checkpoints don't embed label names the way ultralytics `.pt` files do
    (`results[0].names`), so this is required for `rfdetr` and ignored for
    `yolo`.

Example sidecar for an RF-DETR model:

```json
{
  "arch": "rfdetr",
  "variant": "base",
  "classes": ["person", "bicycle", "car", "..."]
}
```

**Failure handling:** malformed JSON, an unknown `arch` value, a missing
`variant`/`classes` for `rfdetr`, or a missing weights file all log an error
and leave the currently-loaded predictor in place — mirroring the existing
`load_model()` behavior ("Sticking with previous model").

## `predictors.py`

```python
class Predictor:
    def __init__(self, weights_path: str, threshold: float, **meta): ...
    def predict(self, image_np: np.ndarray) -> sv.Detections: ...


class YoloPredictor(Predictor):
    # self.model = YOLO(weights_path)
    def predict(self, image_np):
        results = self.model.predict(image_np, conf=self.threshold, verbose=False)
        return sv.Detections.from_ultralytics(results[0])


class RfDetrPredictor(Predictor):
    # self.model = {base: RFDETRBase, large: RFDETRLarge, ...}[variant](pretrain_weights=weights_path)
    # self.classes = meta["classes"]
    def predict(self, image_np):
        detections = self.model.predict(image_np, threshold=self.threshold)
        detections.data["class_name"] = np.array(
            [self.classes[i] for i in detections.class_id]
        )
        return detections


def load_predictor(model_name: str, threshold: float) -> Predictor:
    ...  # sidecar resolution described above, then construct + return
```

Plain classes, no `abc.ABC` — consistent with the rest of the engine's style
(no existing class hierarchies use formal ABCs).

## `openscout_object_engine.py` changes

- `PytorchPredictor` is deleted.
- `__init__` and `load_model()` both call `load_predictor(model_name,
  self.threshold)` and assign the result to `self.detector`.
- `inference()` becomes `self.detector.predict(img)`, returning
  `sv.Detections` directly (no more `self.detector.detection_model.predict(...)`).
- `process_results(image_np, detections, vehicle_info, position_info,
  gimbal_info)` takes `sv.Detections` instead of the raw ultralytics
  `results` list:
  - Exclusions filter: `detections = detections[~np.isin(detections.class_id, exclusions)]`.
    (The redundant confidence re-filter goes away — both backends already
    filter by `threshold` at `predict()` time.)
  - Box normalization: for each `(x1, y1, x2, y2)` in `detections.xyxy`
    (absolute pixel), convert to the existing fractional `[y1, x1, y2, x2]`
    shape using the frame's `image_np.shape` — replacing what
    `to_df(normalize=True)` did for YOLO.
  - Everything after that — geofence check, `geofilter_passed`, HSV filter
    hook, `store_detection_db`, `store_latest_drone_detection_db`, the
    `result_pb2.Detection`/`BoundingBox` construction in `handle()` — is
    **unchanged**, since it still just consumes a plain dict with
    `class`/`score`/`box`/`lat`/`lon`.
- `store_detections_disk()`'s image path drops `results[0].plot()`
  (ultralytics-only) for a small shared helper:

  ```python
  def annotate(image_bgr, detections):
      labels = [
          f"{name} {conf:.2f}"
          for name, conf in zip(detections.data["class_name"], detections.confidence)
      ]
      annotated = sv.BoxAnnotator().annotate(image_bgr.copy(), detections)
      return sv.LabelAnnotator().annotate(annotated, detections, labels=labels)
  ```

  This lives in the engine (not per-backend) since it only operates on the
  common `sv.Detections` format, and gives visually consistent stored images
  regardless of which backend produced the detections.

## Dependencies

`pyproject.toml`: add `rfdetr` and `supervision` (the latter pulled in
transitively by `rfdetr`, but pinned explicitly since the engine imports it
directly). No other dependency changes — `polars` simply stops being
invoked (ultralytics still pulls it transitively; not worth removing as a
direct concern here).

## Implementation notes / risks

Two library-API details should be confirmed against the installed package
versions during implementation, since they were not verified against a live
environment while writing this spec:

- Exact `RFDETR*` class names/constructor kwargs (e.g. whether `num_classes`
  must be passed explicitly alongside `pretrain_weights`, and the exact set
  of variant names) for the installed `rfdetr` version.
- Whether `sv.Detections.from_ultralytics()` populates `.data["class_name"]`
  automatically from `results[0].names` on the installed `supervision`
  version. If not, `YoloPredictor.predict()` needs one extra line to set it
  manually.

## Testing

- New unit tests for `predictors.py`:
  - `load_predictor()` dispatches correctly for: no sidecar (defaults to
    yolo), explicit `"arch": "yolo"`, and `"arch": "rfdetr"` with a valid
    sidecar.
  - `load_predictor()` fails closed (raises/logs, doesn't crash) for
    malformed JSON, unknown `arch`, and a missing `rfdetr` weights file.
  - `YoloPredictor.predict()` and `RfDetrPredictor.predict()` each produce a
    correctly-shaped `sv.Detections` with `class_name` populated — both
    mocking their respective underlying model classes (`ultralytics.YOLO`,
    `RFDETRBase`) rather than requiring real weight files, since checkpoints
    are large binaries unsuitable for test fixtures.
- Existing `test_client.py` / `--unittest` engine flow (disables Redis and
  disk storage) is unaffected, since it doesn't touch the predictor
  backend.
