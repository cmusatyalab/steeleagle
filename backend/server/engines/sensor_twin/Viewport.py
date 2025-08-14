import logging

import numpy as np
from BoundingBox import BoundingBox
from DetectionObject import DetectionObject

import simulator.SensorTwin.sensor_twin_utilities as sensor_twin_utilities
from simulator.SensorTwin.sensor_twin_utilities import Coordinate

ROUNDING_PRECISION = 5
BASE_IMAGE_PATH = "testfiles/testobj.png"
DETECTION_CLASSES = {0: "Car", 1: "Person"}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class Viewport:
    def __init__(
        self,
        drone_name: str,
        drone_type: str,
        global_position: Coordinate,
        orientation: int,
        vertical_rotation: int,
        origin: Coordinate,
    ):
        self.drone_name = drone_name
        self.drone_type = drone_type
        self.position = global_position
        self.cartesian = None
        self.orientation = orientation % 360
        self.vertical_rotation = min(max(0, vertical_rotation), 90)
        self.horizontal_fov = None
        self.vertical_fov = None
        self.diagonal_fov = None
        self.aspect_ratio = None
        self.bounding_box = BoundingBox()
        self.trans_matrix = np.identity(4)
        self.update_cartesian(origin)
        self.update_camera_transform_matrix()

    def get_vertical_cant(self) -> float:
        """
        Returns the current vertical angle of the simulated camera gimble in degrees.
        0 degrees is oriented parallel to a flat horizontal ground plane, 90 degrees
        points perpendicular to the same plane.
        """
        return self.vertical_rotation

    def get_view_orientation(self) -> float:
        """
        Returns the current orientation of the simulated drone in degrees relative to
        true north. Requires conversion to cartesian reference using the utility function
        convert_degree_reference prior to evaluating trig functions.
        """
        return self.orientation

    def get_global_position(self) -> Coordinate:
        return self.position

    def get_absolute_altitude(self) -> float:
        return self.position.alt

    def set_hfov(self, hfov: float):
        if not hfov > 0:
            logger.error(
                f"Attempted to set non-positive horizontal FOV. Value given: {hfov}"
            )
        else:
            self.horizontal_fov = hfov

    def set_vfov(self, vfov: float):
        if not vfov > 0:
            logger.error(
                f"Attempted to set non-positive vertical FOV. Value given: {vfov}"
            )
        else:
            self.vertical_fov = vfov

    def set_dfov(self, dfov: float):
        if not dfov > 0:
            logger.error(
                f"Attempted to set non-positive diagonal FOV. Value given: {dfov}"
            )
        else:
            self.diagonal_fov = dfov

    def set_vertical_cant(self, degrees: float):
        self.vertical_rotation = min(90, max(0, degrees))

    def set_view_orientation(self, degrees: float):
        self.orientation = degrees % 360

    def set_global_position(self, location: Coordinate):
        self.position = location

    def adjust_vertical_cant(self, relative_degrees: float):
        self.set_vertical_cant(self.vertical_rotation + relative_degrees)

    def adjust_view_orientation(self, relative_degrees: float):
        self.set_view_orientation(self.orientation + relative_degrees)

    def adjust_global_position(self, vector: Coordinate, timestep: float):
        scaled_vect = vector.to_vect() * timestep
        new_pos = Coordinate(
            round(self.position.long + scaled_vect[0], ROUNDING_PRECISION),
            round(self.position.lat + scaled_vect[1], ROUNDING_PRECISION),
            round(self.position.alt + scaled_vect[2], ROUNDING_PRECISION),
        )
        self.position = new_pos

    def translate(self, x_trans, y_trans, z_trans):
        self.position.translate(x_trans, y_trans, z_trans)

    def derive_hfov(self):
        if self.vertical_fov is None or self.diagonal_fov is None:
            logger.error(
                "Attempted to calculate horizontal FOV without setting diagonal & vertical FOV"
            )
        else:
            self.horizontal_fov = round(
                sensor_twin_utilities.calc_adjacent(
                    self.diagonal_fov, self.vertical_fov
                ),
                ROUNDING_PRECISION,
            )

    def derive_vfov(self):
        if self.horizontal_fov is None or self.diagonal_fov is None:
            logger.error(
                "Attempted to calculate vertical FOV without setting diagonal & horizontal FOV"
            )
        else:
            self.vertical_fov = round(
                sensor_twin_utilities.calc_adjacent(
                    self.diagonal_fov, self.horizontal_fov
                ),
                ROUNDING_PRECISION,
            )

    def derive_dfov(self):
        if self.horizontal_fov is None or self.vertical_fov is None:
            logger.error(
                "Attempted to calculate diagonal FOV without setting horizontal & vertical FOV"
            )
        else:
            self.diagonal_fov = round(
                sensor_twin_utilities.calc_hypot(
                    self.vertical_fov, self.horizontal_fov
                ),
                ROUNDING_PRECISION,
            )

    def derive_aspect_ratio(self):
        if self.horizontal_fov is None or self.vertical_fov is None:
            logger.error(
                "Unable to calculate aspect ratio without horizontal and vertical fields of view specified"
            )
        else:
            self.aspect_ratio = np.tan(np.deg2rad(self.horizontal_fov / 2)) / np.tan(
                np.deg2rad(self.vertical_fov / 2)
            )

    def magnitude_to_ground(self, degrees) -> float:
        rads = np.deg2rad(min(90.0 - degrees, 89.99))  # TODO: Improve parallel check
        return self.get_absolute_altitude() / np.cos(rads)

    def get_center_point(self) -> Coordinate:
        magnitude = self.magnitude_to_ground(self.get_vertical_cant())
        rads = np.deg2rad(
            sensor_twin_utilities.convert_degree_reference(self.get_view_orientation())
        )
        opp_len = sensor_twin_utilities.calc_opposite(
            magnitude, self.get_absolute_altitude()
        )
        x_offset = np.cos(rads) * opp_len
        y_offset = np.sin(rads) * opp_len
        base = self.get_global_position().to_vect()
        return Coordinate(
            round(base[0] + x_offset, ROUNDING_PRECISION),
            round(base[1] + y_offset, ROUNDING_PRECISION),
            0,
        )

    def get_top_values(self) -> tuple[Coordinate, float]:
        # ASSUMPTION: 0 degrees on gimbal is parallel to horizontal ground plane
        theta = np.deg2rad(
            min(90.0 - (self.get_vertical_cant() - self.vertical_fov / 2), 89.9)
        )
        rads = np.deg2rad(
            sensor_twin_utilities.convert_degree_reference(self.get_view_orientation())
        )
        opp_len = np.tan(theta) * self.get_absolute_altitude()
        x_offset = np.cos(rads) * opp_len
        y_offset = np.sin(rads) * opp_len
        base = self.get_global_position().to_vect()
        return (
            Coordinate(
                round(base[0] + x_offset, ROUNDING_PRECISION),
                round(base[1] + y_offset, ROUNDING_PRECISION),
                0,
            ),
            opp_len,
        )

    def get_bottom_values(self) -> tuple[Coordinate, float]:
        # ASSUMPTION: 0 degrees on gimbal is parallel to horizontal ground plane
        theta = np.deg2rad(90.0 - (self.get_vertical_cant() + self.vertical_fov / 2))
        rads = np.deg2rad(
            sensor_twin_utilities.convert_degree_reference(self.get_view_orientation())
        )
        opp_len = np.tan(theta) * self.get_absolute_altitude()
        x_offset = np.cos(rads) * opp_len
        y_offset = np.sin(rads) * opp_len
        base = self.get_global_position().to_vect()
        return (
            Coordinate(
                round(base[0] + x_offset, ROUNDING_PRECISION),
                round(base[1] + y_offset, ROUNDING_PRECISION),
                0,
            ),
            opp_len,
        )

    def get_lateral_points(
        self, center_point: Coordinate, base_length: float
    ) -> list[Coordinate]:
        base = center_point.to_vect()
        theta = np.deg2rad(
            sensor_twin_utilities.convert_degree_reference(
                self.get_view_orientation() - self.horizontal_fov / 2
            )
        )
        theta_offset = theta - np.deg2rad(90.0 + self.horizontal_fov / 2)
        opp_len = base_length / np.tan(theta)
        x_offset = np.cos(theta_offset) * opp_len
        y_offset = np.sin(theta_offset) * opp_len
        left_corner = Coordinate(
            round(base[0] - x_offset, ROUNDING_PRECISION),
            round(base[1] - y_offset, ROUNDING_PRECISION),
            0,
        )
        right_corner = Coordinate(
            round(base[0] + x_offset, ROUNDING_PRECISION),
            round(base[1] + y_offset, ROUNDING_PRECISION),
            0,
        )
        if theta_offset < 0:
            return (left_corner, right_corner)
        else:
            return (right_corner, left_corner)

    def find_corners(self) -> list[Coordinate]:
        top_point, top_length = self.get_top_values()
        bottom_point, bottom_length = self.get_bottom_values()
        top_corners = self.get_lateral_points(top_point, top_length)
        bot_corners = self.get_lateral_points(bottom_point, bottom_length)
        corners = []
        corners.append(top_corners[0])
        corners.extend(bot_corners)
        corners.append(top_corners[1])
        return corners

    def update_bounding_box(self):
        self.bounding_box.update_orientation(self.get_view_orientation())
        self.bounding_box.update_shape_corners(self.find_corners())

    def check_object(self, detection_object: DetectionObject) -> bool:
        return self.bounding_box.contains(detection_object.get_global_pos())

    def update_cartesian(self, origin):
        self.cartesian = sensor_twin_utilities.wgs_to_cartesian(
            origin, self.get_global_position()
        )

    def update_camera_transform_matrix(self):
        if self.cartesian is None:
            logger.error(
                "Attempted transformation matrix update without setting local cartesian coordinate system"
            )
            return
        # TODO check order of transformations - may need to be scale, rotate, translate not t, r, s
        # Translation TODO verify if these values need to be negative
        self.trans_matrix[0][3] = -self.cartesian[0][0]
        self.trans_matrix[1][3] = -self.cartesian[0][1]
        self.trans_matrix[2][3] = -self.cartesian[0][2]
        # Rotation
        sensor_twin_utilities.rotate_around_z(
            self.trans_matrix,
            sensor_twin_utilities.convert_degree_reference(self.get_view_orientation()),
        )
        sensor_twin_utilities.rotate_around_x(
            self.trans_matrix, self.get_vertical_cant()
        )
        # TODO decide on orientation rotation only or orientation + camera cant rotation
