from utilities import Coordinate
import utilities

CORNER_COUNT = 4

class BoundingBox():
    def __init__(self):
        # Corner Ordering Convention: Top left -> Bottom left -> Bottom right -> Top right
        self.corners = None
        self.orientation = 0.0

    def get_orientation(self):
        return self.orientation
    
    def set_orientation(self, degrees: float):
        self.orientation = degrees % 360

    def update_orientation(self, degrees: float):
        self.orientation = (self.orientation + degrees) % 360

    def translate_shape(self, x_shift, y_shift):
        [x.translate(x_shift, y_shift, 0) for x in self.corners]

    def update_shape_corners(self, new_corners: list[Coordinate]):
        assert len(new_corners) == CORNER_COUNT, "Expected four corner points during bounding box update"
        self.corners = new_corners

    def contains(self, point: Coordinate):
        for i in range(CORNER_COUNT):
            if utilities.line_side_test(self.corners[i], self.corners[i % CORNER_COUNT], point) == False:
                return False
        return True