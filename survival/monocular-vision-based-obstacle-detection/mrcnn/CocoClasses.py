"""
File holding everything related to the MS COCO classes
"""

from dataclasses import dataclass


@dataclass
class CocoClass:
    """
    Class specifying a specific object type that can be recognized by Mask R-CNN
    """

    class_name: str  # class_name = type of object
    static: bool  # static = object may be static or dynamic
    rl_dimensions: tuple  # approximate real life dimensions in x and y in cm


coco_classes = [
    CocoClass("BG", True, (100, 100)),  # Background
    CocoClass("person", False, (60, 180)),
    CocoClass("bicycle", False, (150, 100)),
    CocoClass("car", False, (300, 170)),
    CocoClass("motorcycle", False, (180, 120)),
    CocoClass("airplane", False, (7500, 1500)),
    CocoClass("bus", False, (1000, 250)),
    CocoClass("train", False, (1000, 300)),
    CocoClass("truck", False, (1000, 250)),
    CocoClass("boat", False, (1000, 200)),
    CocoClass("traffic light", True, (100, 40)),
    CocoClass("fire hydrant", True, (100, 20)),
    CocoClass("stop sign", True, (90, 90)),
    CocoClass("parking meter", True, (100, 15)),
    CocoClass("bench", True, (150, 100)),
    CocoClass("bird", False, (20, 15)),
    CocoClass("cat", False, (40, 20)),
    CocoClass("dog", False, (60, 40)),
    CocoClass("horse", False, (200, 180)),
    CocoClass("sheep", False, (120, 90)),
    CocoClass("cow", False, (200, 150)),
    CocoClass("elephant", False, (300, 220)),
    CocoClass("bear", False, (150, 150)),
    CocoClass("zebra", False, (200, 170)),
    CocoClass("giraffe", False, (350, 200)),
    CocoClass("backpack", False, (40, 60)),
    CocoClass("umbrella", False, (100, 50)),
    CocoClass("handbag", False, (40, 30)),
    CocoClass("tie", False, (10, 50)),
    CocoClass("suitcase", False, (80, 80)),
    CocoClass("frisbee", False, (25, 10)),
    CocoClass("skis", False, (100, 100)),
    CocoClass("snowboard", False, (100, 100)),
    CocoClass("sports ball", False, (20, 20)),
    CocoClass("kite", False, (50, 60)),
    CocoClass("baseball bat", False, (100, 100)),
    CocoClass("baseball glove", False, (25, 25)),
    CocoClass("skateboard", False, (80, 80)),
    CocoClass("surfboard", False, (200, 200)),
    CocoClass("tennis racket", False, (50, 50)),
    CocoClass("bottle", False, (30, 15)),
    CocoClass("wine glass", False, (20, 8)),
    CocoClass("cup", False, (10, 10)),
    CocoClass("fork", False, (12, 12)),
    CocoClass("knife", False, (12, 12)),
    CocoClass("spoon", False, (12, 12)),
    CocoClass("bowl", False, (15, 15)),
    CocoClass("banana", False, (15, 15)),
    CocoClass("apple", False, (10, 10)),
    CocoClass("sandwich", False, (15, 15)),
    CocoClass("orange", False, (10, 10)),
    CocoClass("broccoli", False, (10, 10)),
    CocoClass("carrot", False, (10, 10)),
    CocoClass("hot dog", False, (10, 10)),
    CocoClass("pizza", False, (20, 20)),
    CocoClass("donut", False, (10, 10)),
    CocoClass("cake", False, (25, 25)),
    CocoClass("chair", True, (50, 110)),
    CocoClass("couch", True, (200, 100)),
    CocoClass("potted plant", True, (30, 50)),
    CocoClass("bed", True, (150, 150)),
    CocoClass("dining table", True, (150, 100)),
    CocoClass("toilet", True, (60, 50)),
    CocoClass("tv", True, (120, 100)),
    CocoClass("laptop", True, (45, 40)),
    CocoClass("mouse", False, (10, 10)),
    CocoClass("remote", False, (12, 12)),
    CocoClass("keyboard", True, (30, 30)),
    CocoClass("cell phone", False, (10, 10)),
    CocoClass("microwave", True, (50, 40)),
    CocoClass("oven", True, (80, 80)),
    CocoClass("toaster", True, (25, 20)),
    CocoClass("sink", True, (40, 40)),
    CocoClass("refrigerator", True, (80, 120)),
    CocoClass("book", False, (20, 20)),
    CocoClass("clock", True, (20, 20)),
    CocoClass("vase", True, (15, 20)),
    CocoClass("scissors", False, (12, 12)),
    CocoClass("teddy bear", False, (20, 20)),
    CocoClass("hair drier", False, (25, 25)),
    CocoClass("toothbrush", False, (10, 10)),
]


def get_class_name_for_id(class_id):
    """
    :returns a class name to a given class id
    Id is the position of a class in the above list
    """
    return coco_classes[class_id].class_name


def is_static(class_name):
    """
    :returns whether a class can be seen as static or not (dynamic)
    """
    coco_class = next(filter(lambda cls: cls.class_name == class_name, coco_classes))
    return coco_class.static


def get_dimensions(class_name):
    """
    :returns the approximate dimensions of an object in cm
    """
    coco_class = next(filter(lambda cls: cls.class_name == class_name, coco_classes))
    return coco_class.rl_dimensions
