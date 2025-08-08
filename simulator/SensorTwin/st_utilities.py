import numpy as np

class Coordinate():
    def __init__(self, x: float, y: float, alt: float):
        self.long = x
        self.lat = y
        self.alt = alt
    
    def to_vect(self):
        vect = np.zeros(3)
        vect[0] = self.long
        vect[1] = self.lat
        vect[2] = self.alt
        return vect

    def get_distance(self, ref_point: 'Coordinate'):
        mag_vect = self.to_vect() - ref_point.to_vect()
        return np.linalg.norm(mag_vect)

    def translate(self, x_trans: float, y_trans: float, z_trans: float):
        self.long += x_trans
        self.lat += y_trans
        self.alt += z_trans

    def scale(self, x_scale: float, y_scale: float, z_scale: float):
        self.long *= x_scale
        self.lat *= y_scale
        self.alt *= z_scale

    def set_global_pos(self, x: float, y: float, z: float):
        self.long = x
        self.lat = y
        self.alt = z

    def __eq__(self, other):
        if type(self) != type(other):
            return False
        if self.long == other.long and self.lat == other.lat and self.alt == other.alt:
            return True
        return False

    def __sub__(self, other):
        return Coordinate(self.long - other.long, self.lat - other.lat, self.alt - other.alt)

    def __repr__(self):
        return f"({self.long}, {self.lat}, {self.alt})"

class TransformationMatrix():
    def __init__(self, x: float, y: float, z: float):
        self.matrix = np.zeros((4,4))
        np.fill_diagonal(self.matrix, 1)
        self.matrix[0][3] = x
        self.matrix[1][3] = y
        self.matrix[2][3] = z
    
    def __repr__(self):
        return f"{self.matrix[0]}\n{self.matrix[1]}\n{self.matrix[2]}\n{self.matrix[3]}"
    
    def x_trans(self, x_t: float):
        self.matrix[0][3] += x_t

    def y_trans(self, y_t: float):
        self.matrix[1][3] += y_t

    def z_trans(self, z_t: float):
        self.matrix[2][3] += z_t


def normalize_vect(vector: Coordinate) -> Coordinate:
    v_len = np.linalg.norm(vector.to_vect())
    if (v_len != 0):
        len_inverse = 1 / v_len
        norm = Coordinate(vector.long, vector.lat, vector.alt)
        return norm.scale(len_inverse, len_inverse, len_inverse)
    return vector

def calc_opposite(hypot_len: float, adj_len: float) -> float:
    return np.sqrt(hypot_len * hypot_len - adj_len * adj_len)

def calc_adjacent(hypot_len: float, opp_len: float) -> float:
    return np.sqrt(hypot_len * hypot_len - opp_len * opp_len)

def calc_hypot(adj_len: float, opp_len: float) -> float:
    return np.sqrt(opp_len * opp_len + adj_len * adj_len)

def convert_degree_reference(degrees: float) -> float:
    return (450 - degrees) % 360

def cross(base_corner: Coordinate, end_corner: Coordinate, ref_point: Coordinate) -> float:
    return ((ref_point.long - base_corner.long) * (end_corner.lat - base_corner.lat)) - ((ref_point.lat - base_corner.lat) * (end_corner.long - base_corner.long))

def line_side_test(base_corner: Coordinate, end_corner: Coordinate, ref_point: Coordinate):
    cross_prod = cross(base_corner, end_corner, ref_point)
    # Convention: False if ref point is right of the line segment, true if on or to the left
    if cross_prod < 0:
        return False
    else:
        return True

def haversine(origin: Coordinate, ref_point: Coordinate) -> tuple[float, float]:
    EARTH_RADIUS_M = 6371000
    o_phi = np.deg2rad(origin.lat)
    r_phi = np.deg2rad(ref_point.lat)
    d_phi = np.deg2rad(ref_point.lat - origin.lat)
    d_lamba = np.deg2rad(ref_point.long - origin.long)

    a = np.power(np.sin(d_phi / 2.0), 2) + np.cos(o_phi) * np.cos(r_phi) * np.power(np.sin(d_lamba / 2.0), 2)
    c = 2 * np.atan2(np.sqrt(a), np.sqrt(1.0 - a))
    dist = EARTH_RADIUS_M * c

    x = np.cos(o_phi) * np.sin(r_phi) - np.sin(o_phi) * np.cos(r_phi) * np.cos(d_phi)
    y = np.sin(d_lamba) * np.cos(r_phi)
    azimuth = (360.0 + np.rad2deg(np.atan2(y, x))) % 360 #TODO Verify that this is not offset 90 degrees from navigational north

    return (dist, azimuth)

def long_component(dist: float, azimuth: float) -> float:
    return np.cos(azimuth) * dist

def lat_component(dist: float, azimuth: float) -> float:
    return np.sin(azimuth) * dist

def wgs_to_cartesian(origin: Coordinate, ref_point: Coordinate) -> np.ndarray:
    dist, azimuth = haversine(origin, ref_point)
    x_len = long_component(dist, azimuth)
    y_len = lat_component(dist, azimuth)
    return np.array([[x_len, y_len, ref_point.alt - origin.alt]])

def rotate_around_x(target_matrix: np.ndarray, degrees: float) -> np.ndarray:
    rads = np.deg2rad(degrees)
    rotation_matrix = np.array(
        [1, 0, 0, 0],
        [0, np.cos(rads), -np.sin(rads), 0],
        [0, np.sin(rads), np.cos(rads), 0],
        [0, 0, 0, 1]
    )
    return rotation_matrix @ target_matrix

def rotate_around_y(target_matrix: np.ndarray, degrees: float) -> np.ndarray:
    rads = np.deg2rad(degrees)
    rotation_matrix = np.array(
        [np.cos(rads), 0, -np.sin(rads), 0],
        [0, 1, 0, 0],
        [np.sin(rads), 0, np.cos(rads), 0],
        [0, 0, 0, 1]
    )
    return rotation_matrix @ target_matrix

def rotate_around_z(target_matrix: np.ndarray, degrees: float) -> np.ndarray:
    rads = np.deg2rad(degrees)
    rotation_matrix = np.array(
        [np.cos(rads), -np.sin(rads), 0, 0],
        [np.sin(rads), np.cos(rads), 0, 0],
        [0, 0, 1, 0],
        [0, 0, 0, 1]
    )
    return rotation_matrix @ target_matrix

def scale_matrix(target_matrix: np.ndarray, x_factor: float, y_factor: float, z_factor: float) -> np.ndarray:
    scale_mat = np.array(
        [x_factor, 0, 0, 0],
        [0, y_factor, 0, 0],
        [0, 0, z_factor, 0],
        [0, 0, 0, 1]
    )
    return scale_mat @ target_matrix

def translate_matrix(target_matrix: np.ndarray, x_trans: float, y_trans: float, z_trans: float) -> np.ndarray:
    trans_mat = np.array(
        [1, 0, 0, x_trans],
        [0, 1, 0, y_trans],
        [0, 0, 1, z_trans],
        [0, 0, 0, 1]
    )
    return trans_mat @ target_matrix