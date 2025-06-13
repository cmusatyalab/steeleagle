import logging
import numpy as np
from utilities import Coordinate
import utilities
from BoundingBox import BoundingBox

ROUNDING_PRECISION = 5

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class Viewport():
    def __init__(self, g_position: Coordinate, orientation: int, vertical_rotation: int):
        self.position = g_position
        self.orientation = orientation % 360
        self.vertical_rotation = min(max(0, vertical_rotation), 90)
        self.horizontal_fov = None
        self.vertical_fov = None
        self.diagonal_fov = None
        self.aspect_ratio = None
        self.bounding_box = BoundingBox()
    
    def get_vertical_cant(self) -> float:
        '''
        Returns the current vertical angle of the simulated camera gimble in degrees.
        0 degrees is oriented parallel to a flat horizontal ground plane, 90 degrees
        points perpendicular to the same plane.
        '''
        return self.vertical_rotation
    
    def get_view_orientation(self) -> float:
        '''
        Returns the current orientation of the simulated drone in degrees relative to
        true north. Requires conversion to cartesian reference using the utility function
        convert_degree_reference prior to evaluating trig functions.
        '''
        return self.orientation
    
    def get_global_position(self) -> Coordinate:
        return self.position

    def get_absolute_altitude(self) -> float:
        return self.position.alt

    def set_hfov(self, hfov: float):
        if not hfov > 0:
            logger.error(f"Attempted to set non-positive horizontal FOV. Value given: {hfov}")
        else:
            self.horizontal_fov = hfov
    
    def set_vfov(self, vfov: float):
        if not vfov > 0:
            logger.error(f"Attempted to set non-positive vertical FOV. Value given: {vfov}")
        else:
            self.vertical_fov = vfov
    
    def set_dfov(self, dfov: float):
        if not dfov > 0:
            logger.error(f"Attempted to set non-positive diagonal FOV. Value given: {dfov}")
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
        new_pos = Coordinate(round(self.position.long + scaled_vect[0], ROUNDING_PRECISION),
            round(self.position.lat + scaled_vect[1], ROUNDING_PRECISION), round(self.position.alt + scaled_vect[2], ROUNDING_PRECISION))
        self.position = new_pos

    def translate(self, x_trans, y_trans, z_trans):
        self.position.translate(x_trans, y_trans, z_trans)

    def derive_hfov(self):
        if self.vertical_fov == None or self.diagonal_fov == None:
            logger.error("Attempted to calculate horizontal FOV without setting diagonal & vertical FOV")
        else:
            self.horizontal_fov = round(utilities.calc_adjacent(self.diagonal_fov, self.vertical_fov), ROUNDING_PRECISION)
    
    def derive_vfov(self):
        if self.horizontal_fov == None or self.diagonal_fov == None:
            logger.error("Attempted to calculate vertical FOV without setting diagonal & horizontal FOV")
        else:
            self.vertical_fov = round(utilities.calc_adjacent(self.diagonal_fov, self.horizontal_fov), ROUNDING_PRECISION)
    
    def derive_dfov(self):
        if self.horizontal_fov == None or self.vertical_fov == None:
            logger.error("Attempted to calculate diagonal FOV without setting horizontal & vertical FOV")
        else:
            self.diagonal_fov = round(utilities.calc_hypot(self.vertical_fov, self.horizontal_fov), ROUNDING_PRECISION)
    
    def derive_aspect_ratio(self):
        if self.horizontal_fov == None or self.vertical_fov == None:
            logger.error("Unable to calculate aspect ratio without horizontal and vertical fields of view specified")
        else:
            self.aspect_ratio = np.tan(np.deg2rad(self.horizontal_fov / 2)) / np.tan(np.deg2rad(self.vertical_fov / 2))

    def magnitude_to_ground(self, degrees) -> float:
        rads = np.deg2rad(min(90.0 - degrees, 89.99)) # TODO: Improve parallel check
        return self.get_absolute_altitude() / np.cos(rads)

    def get_center_point(self) -> Coordinate:
        magnitude = self.magnitude_to_ground(self.get_vertical_cant())
        rads = np.deg2rad(utilities.convert_degree_reference(self.get_view_orientation()))
        opp_len = utilities.calc_opposite(magnitude, self.get_absolute_altitude())
        x_offset = np.cos(rads) * opp_len
        y_offset = np.sin(rads) * opp_len
        base = self.get_global_position().to_vect()
        return Coordinate(round(base[0] + x_offset, ROUNDING_PRECISION), round(base[1] + y_offset, ROUNDING_PRECISION), 0)

    def get_top_values(self) -> tuple[Coordinate, float]:
        # ASSUMPTION: 0 degrees on gimbal is parallel to horizontal ground plane
        theta = np.deg2rad(max(self.get_view_orientation() - self.vertical_fov / 2), 0.01)
        rads = np.deg2rad(utilities.convert_degree_reference(self.get_view_orientation()))
        opp_len = np.tan(theta) * self.get_absolute_altitude()
        x_offset = np.cos(rads) * opp_len
        y_offset = np.sin(rads) * opp_len
        base = self.get_global_position().to_vect()
        return (Coordinate(round(base[0] + x_offset, ROUNDING_PRECISION), round(base[1] + y_offset, ROUNDING_PRECISION), 0), opp_len)
    
    def get_bottom_values(self) -> tuple[Coordinate, float]:
        # ASSUMPTION: 0 degrees on gimbal is parallel to horizontal ground plane
        theta = np.deg2rad(max(self.get_view_orientation() + self.vertical_fov / 2), 0.01)
        rads = np.deg2rad(utilities.convert_degree_reference(self.get_view_orientation()))
        opp_len = np.tan(theta) * self.get_absolute_altitude()
        x_offset = np.cos(rads) * opp_len
        y_offset = np.sin(rads) * opp_len
        base = self.get_global_position().to_vect()
        return (Coordinate(round(base[0] + x_offset, ROUNDING_PRECISION), round(base[1] + y_offset, ROUNDING_PRECISION), 0), opp_len)
    
    def get_lateral_points(self, center_point: Coordinate, base_length: float) -> list[Coordinate]:
        base = center_point.to_vect()
        theta = np.deg2rad(utilities.convert_degree_reference(self.get_view_orientation() + self.horizontal_fov / 2))
        opp_len = np.tan(theta) * base_length
        theta_offset = theta + np.deg2rad(90 - self.horizontal_fov / 2)
        x_offset = np.cos(theta_offset) * opp_len
        y_offset = np.sin(theta_offset) * opp_len
        left_corner = Coordinate(round(base[0] + x_offset, ROUNDING_PRECISION), round(base[1] + y_offset, ROUNDING_PRECISION), 0)
        right_corner = Coordinate(round(base[0] - x_offset, ROUNDING_PRECISION), round(base[1] - y_offset, ROUNDING_PRECISION), 0)
        return (left_corner, right_corner)
    
    def find_corners(self) -> list[Coordinate]:
        top_point, top_length = self.get_top_values()
        bottom_point, bottom_length = self.get_bottom_values()
        corners = self.get_lateral_points(top_point, top_length)
        corners.extend(self.get_lateral_points(bottom_point, bottom_length))
        return corners

    def update_bounding_box(self):
        self.bounding_box.update_orientation(self.get_view_orientation())
        self.bounding_box.update_shape_corners(self.find_corners())

    '''
    DEPRECATED

    def get_top_intercept(self):
        magnitude = self.magnitude_to_ground(self.get_vertical_cant() - self.vertical_fov / 2)
        rads = np.deg2rad(utilities.convert_degree_reference(self.get_view_orientation()))
        opp_len = utilities.calc_opposite(magnitude, self.get_absolute_altitude())
        x_offset = np.cos(rads) * opp_len
        y_offset = np.sin(rads) * opp_len
        base = self.get_global_position().to_vect()
        return Coordinate(round(base[0] + x_offset, ROUNDING_PRECISION), round(base[1] + y_offset, ROUNDING_PRECISION), 0)

    def get_bottom_intercept(self):
        magnitude = self.magnitude_to_ground(self.get_vertical_cant() + self.vertical_fov / 2)
        rads = np.deg2rad(utilities.convert_degree_reference(self.get_view_orientation()))
        opp_len = utilities.calc_opposite(magnitude, self.get_absolute_altitude())
        x_offset = np.cos(rads) * opp_len
        y_offset = np.sin(rads) * opp_len
        base = self.get_global_position().to_vect()
        return Coordinate(round(base[0] + x_offset, ROUNDING_PRECISION), round(base[1] + y_offset, ROUNDING_PRECISION), 0)
    
    def get_left_intercept(self, centerpoint_mag: float, centerpoint: Coordinate):
        rads = np.deg2rad(utilities.convert_degree_reference(self.get_view_orientation()) - self.horizontal_fov / 2)
        opp_len = centerpoint_mag * np.tan(rads)
        x_offset = np.cos(rads) * opp_len
        y_offset = np.cos(rads) * opp_len
        return Coordinate(round(centerpoint.long + x_offset, ROUNDING_PRECISION), round(centerpoint.lat + y_offset, ROUNDING_PRECISION), 0)

    def get_right_intercept(self, centerpoint_mag: float, centerpoint: Coordinate):
        rads = np.deg2rad(utilities.convert_degree_reference(self.get_view_orientation()) - self.horizontal_fov / 2)
        opp_len = centerpoint_mag * np.tan(rads)
        x_offset = np.cos(rads) * opp_len
        y_offset = np.cos(rads) * opp_len
        return Coordinate(round(centerpoint.long + x_offset, ROUNDING_PRECISION), round(centerpoint.lat + y_offset, ROUNDING_PRECISION), 0)
'''