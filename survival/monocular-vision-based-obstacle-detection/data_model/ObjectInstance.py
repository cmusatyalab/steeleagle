import math
from dataclasses import dataclass, field
from typing import Tuple, Optional

import cv2
import numpy as np
from cv2 import KeyPoint

from Constants import MATCHER_TYPE, MatcherType, CAMERA_TYPE, VIDEO_SCALE
from mrcnn.CocoClasses import get_class_name_for_id, get_dimensions

# Specifies which matcher will be used
if MATCHER_TYPE == MatcherType.SIFT:
    from matcher.SiftMatcher import average_descriptor_distance, get_keypoints_and_descriptors_for_object
elif MATCHER_TYPE == MatcherType.SURF:
    from matcher.SurfMatcher import average_descriptor_distance, get_keypoints_and_descriptors_for_object
else:
    from matcher.OrbMatcher import average_descriptor_distance, get_keypoints_and_descriptors_for_object

from data_model.Box import Box
from utils.timer import timing


@dataclass
class ObjectInstance:
    """
    Class holding an individual object occurrence.
    """

    class_name: str
    roi: Box
    confidence_score: float
    translation_to_last_instance: Optional[Tuple[float, float, float]]
    velocity: Optional[Tuple[float, float, float]]
    speed: Optional[float]
    mask: [[]]
    keypoints: [KeyPoint] = field(default_factory=list)
    descriptors: np.ndarray = None

    def similarity_to(self, obj_instance) -> float:
        """
        :returns value in range of [0, 1] whether this object is similar to the incoming obj_instance.
        0 => Not similar
        1 => Very similar
        """
        # Check if both have descriptors
        if self.descriptors is None or obj_instance.descriptors is None:
            return 0
        # Check if descriptors match
        average_distance = average_descriptor_distance(self.descriptors, obj_instance.descriptors)
        return max(0.0, 1 - average_distance)

    def approximate_distance(self) -> float:
        """:returns rough estimation of distance to the object in meters"""
        rl_dim_x, rl_dim_y = get_dimensions(self.class_name)
        lens_factor = CAMERA_TYPE.value[0] * VIDEO_SCALE
        bbox = self.roi
        if bbox.out_of_frame_left() or bbox.out_of_frame_right():
            # bbox goes out of frame horizontally
            return self._approximate_distance_vertically(bbox, lens_factor, rl_dim_y)
        elif bbox.out_of_frame_top() or bbox.out_of_frame_bottom():
            # bbox goes out of frame vertically
            return self._approximate_distance_horizontally(bbox, lens_factor, rl_dim_x)
        else:
            approx_distance_vertically = self._approximate_distance_vertically(bbox, lens_factor, rl_dim_y)
            approx_distance_horizontally = self._approximate_distance_horizontally(bbox, lens_factor, rl_dim_x)
            return min(approx_distance_vertically, approx_distance_horizontally)  # one dimension could be occluded

    def _approximate_distance_horizontally(self, bbox, lens_factor, rl_dim_x):
        return (rl_dim_x * lens_factor) / bbox.get_width()

    def _approximate_distance_vertically(self, bbox, lens_factor, rl_dim_y):
        return (rl_dim_y * lens_factor) / bbox.get_height()

    def get_3d_position(self) -> tuple:
        """
        :returns the approximate position of this object instance in 3d coordinates (x,y,z) in meters
        relative to the camera. The camera coordinates are defined as (0,0,0).
        x: negative is left in picture, positive is right
        y: negative is down in picture, positive is up
        z: negative is behind the camera (should never happen), positive is straight into the picture
        """
        distance = self.approximate_distance()
        angle_x_degree = (self.roi.get_position_in_image()[0] - 0.5) * CAMERA_TYPE.value[1]
        angle_y_degree = (self.roi.get_position_in_image()[1] - 0.5) * CAMERA_TYPE.value[2]
        angle_x_radian = angle_x_degree * math.pi / 180 + math.pi / 2
        angle_y_radian = angle_y_degree * math.pi / 180 + math.pi / 2
        x = -(distance * math.sin(angle_y_radian) * math.cos(angle_x_radian))
        y = distance * math.cos(angle_y_radian)
        z = distance * math.sin(angle_y_radian) * math.sin(angle_x_radian)
        return x, y, z

    def __str__(self):
        return f"{self.class_name}, " \
               f"center: {self.roi.get_center()}, " \
               f"distance: {self.approximate_distance():.1f}, " \
               f"3d pos: {self.get_3d_position()}"


@timing
def create_objects(result, frame) -> [ObjectInstance]:
    """
    Generates list of ObjectInstances from the results obtained by Mask R-CNN and the current frame.
    """
    objects = []
    number_of_results = result["class_ids"].shape[0]

    # Convert frame to grayscale for matchers
    frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    for i in range(number_of_results):

        confidence_score = result["scores"][i]
        class_name = get_class_name_for_id(result["class_ids"][i])

        roi = result["rois"][i]
        y1, x1, y2, x2 = roi
        box = Box(x1, y1, x2, y2)

        mask = result["masks"][:, :, i].astype(np.uint8)

        keypoints, descriptors = get_keypoints_and_descriptors_for_object(frame_gray, mask)
        # show(drawKeypoints(frame, keypoints, None))
        detected_object = ObjectInstance(class_name,
                                         box,
                                         confidence_score,
                                         translation_to_last_instance=None,
                                         velocity=None,
                                         speed=None,
                                         mask=mask,
                                         keypoints=keypoints,
                                         descriptors=descriptors)
        objects.append(detected_object)

    return objects
