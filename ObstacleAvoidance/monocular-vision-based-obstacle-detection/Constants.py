import os
from enum import Enum


class InputDataType(Enum):
    VIDEO = "VIDEO"
    IMAGE = "IMAGE"

    def __str__(self):
        return self.name


class MatcherType(Enum):
    SIFT = "SIFT"
    ORB = "ORB"
    SURF = "SURF"

    def __str__(self):
        return self.name


class CameraType(Enum):
    # 1. value: Lens factor: image pixels per cm at 1m distance in real world
    # 2. value: Field of view horizontal: Field of view in degrees in x dimension
    # 3. value: Field of view vertical: Field of view in degrees in y dimension
    IPHONE_8_PLUS_4K_60 = (32.8, 66, 40)  # rough estimation
    IPHONE_XR_4K_60 = (31.2, 62.76, 38.58)
    FL2_14S3C_C = (7.1, 90, 35)  # Camera used in kitti dataset

    def __str__(self):
        return self.name


INPUT_PATH = "no path set"
INPUT_DATA_TYPE = InputDataType.VIDEO
INPUT_DIMENSIONS = (1920, 1080)
INPUT_FPS = 60
OUTPUT_FPS = 10
FROM_SEC_OR_IMAGE = 0
TO_SEC_OR_IMAGE = 2
MATCHER_TYPE = MatcherType.SIFT
VIDEO_SCALE = 1
CAMERA_TYPE = CameraType.IPHONE_XR_4K_60

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
