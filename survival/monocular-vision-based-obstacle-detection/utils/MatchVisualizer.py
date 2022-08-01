"""
Match Visualizer

Helper class that is used to visualize keypoint matches for two given images.
Only used for visualization purposes.
"""

import os

import cv2

from Constants import ROOT_DIR

from Constants import MATCHER_TYPE, MatcherType

if MATCHER_TYPE == MatcherType.SIFT:
    from matcher.SiftMatcher import get_matches
elif MATCHER_TYPE == MatcherType.SURF:
    from matcher.SurfMatcher import get_matches
else:
    from matcher.OrbMatcher import get_matches

from data_model.DetectedObjects import DetectedObjects
from data_model.ObjectInstance import create_objects
from mrcnn.Mask_R_CNN_COCO import detect
from utils.image_utils import show
import numpy as np

IMAGE_PATH_1 = os.path.join(ROOT_DIR, "data/testImages/000000.png")
IMAGE_PATH_2 = os.path.join(ROOT_DIR, "data/testImages/000001.png")

if __name__ == "__main__":

    detected_objects = DetectedObjects()

    image_1 = cv2.imread(IMAGE_PATH_1)
    image_2 = cv2.imread(IMAGE_PATH_2)

    print("detecting objects in image 1")
    result_1 = detect(image_1)
    print("detecting objects in image 2")
    result_2 = detect(image_2)

    objects_1 = create_objects(result_1, image_1)
    objects_2 = create_objects(result_2, image_2)

    if not objects_1 or not objects_2:
        print("Not enough objects found")

    detected_objects.add_objects(objects_1)
    detected_objects.add_objects(objects_2)

    for obj_id, detected_object in detected_objects.objects.items():
        if len(detected_object.occurrences) == 2 \
                and detected_object.occurrences[0] is not None \
                and detected_object.occurrences[1] is not None:

            obj_instance_1 = detected_object.occurrences[0]
            obj_instance_2 = detected_object.occurrences[1]

            for dist in np.linspace(100, 1000, 5):
                matches = get_matches(obj_instance_1.descriptors, obj_instance_2.descriptors, dist)
                image_with_matches = cv2.drawMatches(image_1, obj_instance_1.keypoints, image_2, obj_instance_2.keypoints, matches, None)
                show(image_with_matches, "Matches: dist=" + str(dist), await_keypress=True)
