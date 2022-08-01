"""
Configuration specific to MS COCO
"""
import os

import mrcnn.model as modellib

# Import Mask RCNN
from Constants import ROOT_DIR, INPUT_DIMENSIONS
from mrcnn import utils

# Local path to trained weights file
from mrcnn.config import Config
from utils.timer import timing

COCO_MODEL_PATH = os.path.join(ROOT_DIR, "weights/mask_rcnn_coco.h5")
# Download COCO trained weights from Releases if needed
if not os.path.exists(COCO_MODEL_PATH):
    utils.download_trained_weights(COCO_MODEL_PATH)


# ## Configurations
#
# We'll be using a model trained on the MS-COCO dataset. The configurations of this model are in the ```CocoConfig``` class.
#
# For inferencing, modify the configurations a bit to fit the task. To do so, sub-class the ```CocoConfig``` class and override the attributes you need to change.
#


class CocoConfig(Config):
    """Configuration for training on MS COCO.
    Derives from the base Config class and overrides values specific
    to the COCO dataset.
    """

    # Give the configuration a recognizable name
    NAME = "coco"

    # We use a GPU with 12GB memory, which can fit two images.
    # Adjust down if you use a smaller GPU.
    IMAGES_PER_GPU = 2

    # Uncomment to train on 8 GPUs (default is 1)
    # GPU_COUNT = 8

    # Number of classes (including background)
    NUM_CLASSES = 1 + 80  # COCO has 80 classes


def find_closest_acceptable_number(number):
    """
    Finds closest number which is six times divisible by 2.
    This is necessary to avoid fractions when downscaling.

    """
    if number % 64 == 0:
        return number
    else:
        multiplier = round(number / 64)
        return 64 * multiplier


class InferenceConfig(CocoConfig):
    # Set batch size to 1 since we'll be running inference on
    # one image at a time. Batch size = GPU_COUNT * IMAGES_PER_GPU
    GPU_COUNT = 1
    IMAGES_PER_GPU = 1
    IMAGE_MIN_DIM = find_closest_acceptable_number(min(INPUT_DIMENSIONS))
    IMAGE_MAX_DIM = find_closest_acceptable_number(max(INPUT_DIMENSIONS))  # TODO: experiment with results and timing to see if its worth to lower this

    DETECTION_MIN_CONFIDENCE = 0.8


config = InferenceConfig()
config.display()

## Create Model and Load Trained Weights
# Create model object in inference mode.
model = modellib.MaskRCNN(mode="inference", model_dir="logs", config=config)

# Load weights trained on MS-COCO
model.load_weights(COCO_MODEL_PATH, by_name=True)


@timing
def detect(image):
    """
    Runs the detection on a given image
    """
    # Run detection
    results = model.detect([image], verbose=0)

    # ignore batch dimension
    return results[0]
