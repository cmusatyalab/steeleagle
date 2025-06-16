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



class DetectionObject():
    def __init__(self, x: float, y: float, alt: float, obj_class: str, base_detection: float, distance_falloff: float, falloff_penalty: float):
        self.location = Coordinate(x, y, alt)
        self.obj_class = obj_class
        self.base_detection = base_detection
        self.falloff = distance_falloff
        self.penalty = falloff_penalty

    def __repr__(self):
        return f"{self.obj_class}: {self.location}"
    
    def calc_confidence(self, reference_point: Coordinate):
        dist = self.get_distance(reference_point)
        return max(self.base_detection - (max(dist - self.falloff, 0) * self.penalty), 0)



def normalize_vect(vector: Coordinate):
    v_len = np.linalg.norm(vector.to_vect())
    if (v_len != 0):
        len_inverse = 1 / v_len
        norm = Coordinate(vector.long, vector.lat, vector.alt)
        return norm.scale(len_inverse, len_inverse, len_inverse)
    return vector

def calc_opposite(hypot_len: float, adj_len: float):
    return np.sqrt(hypot_len * hypot_len - adj_len * adj_len)

def calc_adjacent(hypot_len: float, opp_len: float):
    return np.sqrt(hypot_len * hypot_len - opp_len * opp_len)

def calc_hypot(adj_len: float, opp_len: float):
    return np.sqrt(opp_len * opp_len + adj_len * adj_len)

def convert_degree_reference(degrees: float):
    return (450 - degrees) % 360

def cross(base_corner: Coordinate, end_corner: Coordinate, ref_point: Coordinate):
    return ((ref_point.long - base_corner.long) * (end_corner.lat - base_corner.lat)) - ((ref_point.lat - base_corner.lat) * (end_corner.long - base_corner.long))

def line_side_test(base_corner: Coordinate, end_corner: Coordinate, ref_point: Coordinate):
    cross_prod = cross(base_corner, end_corner, ref_point)
    # Convention: False if ref point is right of the line segment, true if on or to the left
    if cross_prod < 0:
        return False
    else:
        return True