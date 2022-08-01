from dataclasses import dataclass
from Constants import INPUT_DIMENSIONS

OUT_OF_FRAME_MARGIN = 5


@dataclass
class Box:
    """
    Class holding the values of a bounding box.
    x1 = Left
    y1 = Top
    x2 = Right
    y2 = Bottom
    """

    x1: int
    y1: int
    x2: int
    y2: int

    def get_width(self) -> int:
        """
        :return: width of bounding box
        """
        return self.x2 - self.x1

    def get_height(self) -> int:
        """
        :return: height of bounding box
        """
        return self.y2 - self.y1

    def get_center(self) -> tuple:
        """
        :return: center of bounding box as (x, y) in pixel
        """
        return int(self.x1 + self.get_width() / 2), int(self.y1 + self.get_height() / 2)

    def get_position_in_image(self) -> tuple:
        """
        :return: position of bounding box within the image as (x, y)  each with values in the range of [0, 1]
        """
        return self.get_center()[0] / INPUT_DIMENSIONS[0], self.get_center()[1] / INPUT_DIMENSIONS[1]

    def out_of_frame_left(self) -> bool:
        """
        :return: boolean whether the bounding box touches the left frame edge (with some margin)
        """
        return self.x1 < OUT_OF_FRAME_MARGIN

    def out_of_frame_right(self) -> bool:
        """
        :return: boolean whether the bounding box touches the right frame edge (with some margin)
        """
        return self.x2 > INPUT_DIMENSIONS[0] - OUT_OF_FRAME_MARGIN

    def out_of_frame_top(self) -> bool:
        """
        :return: boolean whether the bounding box touches the top frame edge (with some margin)
        """
        return self.y1 < OUT_OF_FRAME_MARGIN

    def out_of_frame_bottom(self) -> bool:
        """
        :return: boolean whether the bounding box touches the bottom frame edge (with some margin)
        """
        return self.y2 > INPUT_DIMENSIONS[1] - OUT_OF_FRAME_MARGIN
