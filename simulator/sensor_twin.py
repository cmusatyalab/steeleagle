import time
import os
import logging
import numpy as np
from utilities import Coordinate, TransformationMatrix
import utilities
from Viewport import Viewport

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

FALLOFF_PENALTY = 10.0

'''
ST File Requirements:
- Origin Position
- Tileset w/ GPS mappings
- X & Y Dimension Lengths
- Drone Model
- Field of View
- Zoom Level
- Target List
    - X & Y Coords
    - Distance Magnitude to Confidence
        - Either modeling function or step function with thresholds and concrete values

Prototype Assumptions:
- Search area is perfectly flat, drone altitude is only var in z-plane
- Square/rectangular tiles
- Focal length is fixed
- Gimbal fixed at single angle?
- SensorTwin replaces detection engine instead of interposing it
- Rectangular bounding boxes
- Detections & confidence intervals are deterministic, not probabilistic

Design Questions
- Expected usage requires full end-to-end? Or simulated Redis/other component access?
- Toy/unit tests for rapid validation of draft sensortwin files?
'''

class SensorTwin():
    def __init__(self, init_file, model, threshold):
        # DB connection?
        # Communication with gabriel?
        pass

    def parse_init_file(self, init_file):
        # Assume YAML -> Convert to dict
        pass

    def select_image(self, lat, long, alt, pitch):
        pass

    def prepare_image(self, target_list, image_slice):
        pass

    def calc_viewport(self, lat, long, alt, pitch, fov, focal_length):
        pass

    def calc_center_distance(self, alt, pitch):
        pass

    def calc_object_distance(self, lat, long, alt, target_object):
        pass

### TESTING LOGIC ###

def test_battery():
    test_obj = Coordinate(0, 1, 2)
    assert test_obj.long == 0 and test_obj.lat == 1 and test_obj.alt == 2, "Failed to construct coordinate"
    test_obj.translate(-1, -1, -1)
    assert test_obj.long == -1 and test_obj.lat == 0 and test_obj.alt == 1, "Failed to translate coordinate"
    test_dist = test_obj.get_distance(Coordinate(0, 0, 0))
    assert test_dist == np.sqrt(2), "Failed to calculate coordinate distances"

    base_mat = np.array([
        [1., 0., 0., 3.],
        [0., 1., 0., 3.],
        [0., 0., 1., 3.],
        [0., 0., 0., 1.]
    ])

    test_mat = TransformationMatrix(3, 3, 3)
    assert np.all(test_mat.matrix == base_mat), "Failed to construct transformation matrix"

    test_vp = Viewport(Coordinate(0, 0, 0), 0, 45)
    test_vp.adjust_global_position(Coordinate(1, 2, 3), 1.0)
    assert test_vp.get_global_position() == Coordinate(1.0, 2.0, 3.0), "Failed to update camera position"
    assert test_vp.get_center_point() == Coordinate(1.0, 5.0, 0.0), "Invalid intercept generation on flat surface"
    test_vp.set_view_orientation(45)
    test_vp.set_vertical_cant(90)
    assert test_vp.magnitude_to_ground(test_vp.get_vertical_cant()) == 3.0, "Invalid ground trace magnitude"
    assert test_vp.get_center_point() == Coordinate(1.0, 2.0, 0.0), "Failed intercept generation perpendicular to surface"

    test_vp.set_hfov(100)
    test_vp.derive_dfov() # Should fail and trigger logging message
    test_vp.set_vfov(60)
    test_vp.derive_dfov()
    test_vp.derive_aspect_ratio()


def main():
    print("Starting test battery")
    test_battery()
    print("Completed test battery")

if __name__ == "__main__":
    main()
