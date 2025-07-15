from st_utilities import Coordinate
import st_utilities as st_utilities

class DetectionObject():
    def __init__(self, x: float, y: float, alt: float, label: str, base_conf: float, falloff_rate: float, falloff_dist: float, length: float, width: float, height: float):
        assert base_conf >= 0.0, "Attempted to set negative base confidence value"
        assert falloff_rate >= 0.0, "Attempted to set negative confidence falloff rate"
        assert falloff_dist >= 0.0, "Attempted to set negative falloff distance threshold"
        self.position = Coordinate(x, y, alt)
        self.length = length
        self.width = width
        self.height = height
        self.cartesian = None
        self.class_label = label
        self.max_confidence = base_conf
        self.falloff_rate = falloff_rate
        self.falloff_dist = falloff_dist
    
    def get_global_pos(self):
        return self.position
    
    def set_global_pos(self, x: float, y: float, alt: float):
        self.position.set_global_pos(x, y, alt)

    def get_confidence(self):
        return self.max_confidence
    
    def set_confidence(self, new_base_conf: float):
        assert new_base_conf >= 0.0, "Attempted to set negative base confidence"
        self.max_confidence = new_base_conf

    def get_detection_confidence(self, ref_point: Coordinate):
        distance = self.position.get_distance(ref_point)
        if (distance <= self.falloff_dist):
            return self.max_confidence
        else:
            return max(0, self.max_confidence - (distance - self.falloff_dist) * self.falloff_rate)
    
    def produce_detection(self, ref_point: Coordinate):
        conf = self.get_detection_confidence(ref_point)
        return (self.class_label, conf)
    
    def update_cartesian(self, origin: Coordinate):
        self.cartesian = st_utilities.wgs_to_cartesian(origin, self.position)

    def get_prism_corners(self):
        g_pos = self.get_global_pos()
        center_x = g_pos.long
        center_y = g_pos.lat
        center_z = g_pos.alt
        corners = []
        x_vals = [center_x - (self.length / 2), center_x + (self.length / 2)]
        y_vals = [center_y - (self.width / 2), center_y + (self.width / 2)]
        z_vals = [center_z - (self.height / 2), center_z + (self.height / 2)]
        for x in x_vals:
            for y in y_vals:
                for z in z_vals:
                    corners.append(Coordinate(x, y, z))
        return corners