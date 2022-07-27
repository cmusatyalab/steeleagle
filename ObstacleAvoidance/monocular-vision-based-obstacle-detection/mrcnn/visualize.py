"""
Mask R-CNN
Display and Visualization Functions.

Copyright (c) 2017 Matterport, Inc.
Licensed under the MIT License (see LICENSE for details)
Written by Waleed Abdulla

Adapted by Johannes Berger
"""

import colorsys
import random

import cv2
import numpy as np

from Constants import VIDEO_SCALE
from data_model.Box import Box
from data_model.DetectedObjects import DetectedObjects
from utils.timer import timing


def random_colors(number_of_colors, bright=True):
    """
    Generate random colors.
    To get visually distinct colors, generate them in HSV space then
    convert to RGB.
    """
    brightness = 1.0 if bright else 0.7
    hsv = [(i / number_of_colors, 1, brightness) for i in range(number_of_colors)]
    colors = list(map(lambda c: colorsys.hsv_to_rgb(*c), hsv))
    random.shuffle(colors)
    colors = [[int(channel * 255) for channel in color] for color in colors]
    return colors


def apply_mask(image, mask, color, alpha=0.5):
    """
    Apply the given mask to the image.
    Color an alpha can be customized
    """
    for channel in range(3):
        image[:, :, channel] = np.where(mask == 1,
                                        image[:, :, channel] * (1 - alpha) + alpha * color[channel],
                                        image[:, :, channel])
    return image


def filtered(class_name) -> bool:
    """
    Filters visualizations to a set of classes that should be shown
    """
    allowed_classes = {"traffic light", "truck", "bus", "motorcycle", "car", "person"}
    # allowed_classes = {"chair", "potted plant", "cup"}
    return class_name not in allowed_classes


@timing
def draw_instances(
    image,
    detected_objects: DetectedObjects,
    show_mask=True,
    show_bbox=True,
    show_label=True,
    show_trajectory=True,
    show_confidence_score=False,
    show_distance=True,
    show_3d_position=False,
    show_kalman_next_prediction_area=False,
    show_kalman_last_prediction_area=True,
):
    """
    image: image to copy and illustrate on
    detected_objects: objects to draw
    show_x: Display various features
    """

    result_image = image.copy()

    for obj_id, obj_track in detected_objects.objects.items():

        if obj_track.is_present() and not filtered(obj_track.class_name):

            current_instance = obj_track.get_current_instance()
            print(
                f"{obj_track.class_name}, "
                f"id: {obj_id}, "
                f"tracked for {len(obj_track.occurrences)} frames, "
                f"3D pos: {tuple(map(lambda e: round(e, 2), current_instance.get_3d_position()))}, "
                f"distance: {current_instance.approximate_distance() :.2f}m, "
                f"velocity: {tuple(map(lambda e: round(e, 2), current_instance.velocity)) if current_instance.velocity is not None else 'None'}, "
                f"speed: {round(current_instance.speed, 2) if current_instance.speed is not None else 'None '}km/h"
            )

            color = static_colors[obj_id % max_number_of_colors]

            # Bounding box
            if not np.any(current_instance.roi):
                # Skip this instance. Has no bbox. Likely lost in image cropping.
                continue
            box: Box = current_instance.roi
            if show_bbox:
                pt1 = (box.x1, box.y1)
                pt2 = (box.x2, box.y2)
                cv2.rectangle(result_image, pt1=pt1, pt2=pt2, color=color, thickness=1)

            # Label
            if show_label:
                class_name = current_instance.class_name
                label_text = f"{class_name} {obj_id}: "
                if show_confidence_score:
                    label_text += f"score: {current_instance.confidence_score : .3f} "
                if show_distance:
                    label_text += f"dist: {current_instance.approximate_distance() : .1f}m "
                if show_3d_position:
                    label_text += f"3D pos: {current_instance.get_3d_position()} "
                cv2.putText(result_image, label_text, (box.x1, box.y1 - 1), fontFace=cv2.FONT_HERSHEY_SIMPLEX, fontScale=0.4, color=(0, 0, 255), thickness=1, lineType=cv2.LINE_AA)

            # Mask
            if show_mask:
                mask = current_instance.mask
                result_image = apply_mask(result_image, mask, color)

            velocity = current_instance.velocity
            if show_trajectory and velocity and len(obj_track.occurrences) > 4:
                # Trajectory based on velocity (amplified for better visualization)
                visualization_factor = 30 * VIDEO_SCALE
                center = box.get_center()
                arrow_head = (int(center[0] + velocity[0] * visualization_factor), int(center[1] + velocity[1] * visualization_factor))
                cv2.arrowedLine(result_image, center, arrow_head, (0, 0, 255), 2)

            # Kalman next step prediction
            if show_kalman_next_prediction_area:
                x, y = obj_track.get_next_position_prediction()
                cov_x, cov_y = obj_track.get_next_position_uncertainty()
                cv2.line(result_image, (x - int(cov_x / 2), y), (x + int(cov_x / 2), y), (0, 255, 0), 1)
                cv2.line(result_image, (x, y - int(cov_y / 2)), (x, y + int(cov_y / 2)), (0, 255, 0), 1)

            # Kalman current step prediction
            if show_kalman_last_prediction_area:
                x, y = obj_track.get_current_position_prediction()
                cov_x, cov_y = obj_track.get_current_position_uncertainty()
                pt1 = (x - int(cov_x / 2), y - int(cov_y / 2))
                pt2 = (x + int(cov_x / 2), y + int(cov_y / 2))
                rect = np.zeros(result_image.shape, np.uint8)
                cv2.rectangle(rect, pt1=pt1, pt2=pt2, color=(0, 255, 0), thickness=1)
                result_image = cv2.addWeighted(result_image, 1.0, rect, 0.25, 1)

    return result_image


@timing
def draw_depth_map(image, detected_objects: DetectedObjects, show_distance=False):
    """
    image: only used for dimensions
    detected_objects: objects to draw depth of
    """

    depth_image = np.zeros(image.shape, dtype=np.uint8)

    for obj_track in detected_objects.objects.values():

        if obj_track.is_present():

            current_instance = obj_track.get_current_instance()
            distance = current_instance.approximate_distance()

            color = [int(max(255 - distance, 0))] * 3

            # Bounding box
            if not np.any(current_instance.roi):
                # Skip this instance. Has no bbox. Likely lost in image cropping.
                continue

            # Label
            if show_distance:
                box: Box = current_instance.roi
                class_name = current_instance.class_name
                label_text = f"{class_name} : {distance :.1f}m"
                cv2.putText(depth_image, label_text, (box.x1, box.y1 - 1), fontFace=cv2.FONT_HERSHEY_SIMPLEX, fontScale=0.4, color=(0, 0, 255), thickness=1, lineType=cv2.LINE_AA)

            # Mask
            mask = current_instance.mask
            depth_image = apply_mask(depth_image, mask, color, alpha=1)

    return depth_image


max_number_of_colors = 30
static_colors = random_colors(max_number_of_colors)
