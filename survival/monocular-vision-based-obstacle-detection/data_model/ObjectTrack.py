import math
import operator
from typing import Optional, Tuple

from Constants import MATCHER_TYPE, MatcherType, INPUT_FPS, CAMERA_TYPE, VIDEO_SCALE
from matcher.KalmanTracker import KalmanTracker
from mrcnn.CocoClasses import is_static

# Specifies which matcher will be used
if MATCHER_TYPE == MatcherType.SIFT:
    from matcher.SiftMatcher import get_matches
elif MATCHER_TYPE == MatcherType.SURF:
    from matcher.SurfMatcher import get_matches
else:
    from matcher.OrbMatcher import get_matches

from data_model.ObjectInstance import ObjectInstance


class ObjectTrack:
    """
    Class which holds all instances of an object found throughout a video
    """

    def __init__(self, first_obj_occurrence: ObjectInstance):
        self.occurrences: [Optional[ObjectInstance]] = [first_obj_occurrence]
        x, y = first_obj_occurrence.roi.get_center()
        self.kalman_tracker: KalmanTracker = KalmanTracker(x, y)
        self.class_name: str = first_obj_occurrence.class_name
        self.active = True  # Boolean whether this object is considered for matching or not

    def add_occurrence(self, new_obj_instance: Optional[ObjectInstance]):
        """
        Add latest occurrence of an object to the object track or None if previously found object wasn't found in the
        current frame.
        """
        self.occurrences.append(new_obj_instance)
        center_or_none = None if new_obj_instance is None else new_obj_instance.roi.get_center()
        self.kalman_tracker.update(center_or_none)
        if self.is_present():
            self.get_current_instance().translation_to_last_instance = self.get_translation_to_last_instance()
            velocity = self.get_velocity()
            speed = self.calculate_speed_from_velocity(velocity)
            self.get_current_instance().velocity = velocity
            self.get_current_instance().speed = speed

    def get_next_position_prediction(self):
        """
        :returns predicted position (x, y) of this object in the next frame
        """
        return self.kalman_tracker.next_position_prediction()

    def get_current_position_prediction(self):
        """
        :returns position prediction (x, y) of this object for the current frame
        """
        return self.kalman_tracker.current_position_prediction()

    def get_next_position_uncertainty(self):
        """
        :returns position uncertainty in x and y direction of this object in the next frame
        """
        return self.kalman_tracker.next_position_uncertainty()

    def get_current_position_uncertainty(self):
        """
        :returns position uncertainty in x and y direction of this object in the current frame
        """
        return self.kalman_tracker.current_position_uncertainty()

    def is_present(self) -> bool:
        """Bool whether object is present in current frame"""
        return len(self.occurrences) > 0 and self.occurrences[-1] is not None

    def was_present_in_last_n_frames(self, n=5) -> bool:
        """Bool whether object was present in the last n frames at least once"""
        last_n_occurrences = self.occurrences[-n:]
        return any(last_n_occurrences)  # checks if any is not None

    def get_current_instance(self) -> ObjectInstance:
        """
        :return: current instance if present, else None
        """
        return self.occurrences[-1] if self.is_present() else None

    def similarity_to(self, obj_instance: ObjectInstance, over_n_instances: int = 5) -> float:
        """
        Returns a value in the range of [0, 1] whether the incoming obj_instance is similar to this object.
        0 => Not similar
        1 => Very similar
        """
        # Check if same class
        if not self.class_name == obj_instance.class_name:
            return 0
        # Check if location checks out
        if not self.kalman_tracker.is_point_in_predicted_area(obj_instance.roi.get_center()):
            return 0
        last_n_occurrences = self.occurrences[-over_n_instances:]
        for occurrence in reversed(last_n_occurrences):
            if occurrence is not None:
                return occurrence.similarity_to(obj_instance)
        # Object did not appear in last 5 frames
        return 0

    def is_static(self):
        """
        :returns whether an object is stationary like a traffic light or not
        """
        return is_static(self.class_name)

    def get_velocity(self, over_n_instances: int = INPUT_FPS):
        """
        Calculates the velocity for the axis x, y, and z in m/s
        Returns None if object did not appear in the current frame
        """
        if not self.active or not self.is_present():
            return None
        else:
            last_n_occurrences = self.occurrences[-over_n_instances:]  # Getting last (max) n occurrences of this object
            last_n_occurrences_filtered = [x for x in last_n_occurrences if x is not None]  # Filtering for non None values
            last_translations = list(map(lambda x: x.translation_to_last_instance, last_n_occurrences_filtered))  # mapping to positions of this object
            last_translations_filtered = [x for x in last_translations if x is not None]  # Filtering for non None values
            cumulative_translation = tuple(map(sum, zip(*last_translations_filtered)))  # Adding up all the differences
            smoothed_translation = tuple(map(lambda x: x / (len(last_n_occurrences) - 1), cumulative_translation))  # dividing by number of instances / frames since first appearance
            translation_in_meter_per_second = tuple(map(lambda x: x * INPUT_FPS, smoothed_translation))  # Multiplying by fps to get m/s
            return translation_in_meter_per_second

    def calculate_speed_from_velocity(self, velocity) -> Optional[float]:
        """Returns the current estimated speed in km/h if a velocity could be calculated beforehand, else None"""
        return None if velocity is None else math.sqrt(sum([e ** 2 for e in velocity])) * 3.6

    def get_previous_present_instance(self) -> Optional[ObjectInstance]:
        """Returns the last present occurrence or None if there was none"""
        all_but_current_instance = list(reversed(self.occurrences[:-1]))
        for instance in all_but_current_instance:
            if instance is not None:
                return instance

    def get_translation_to_last_instance(self) -> Optional[Tuple[float, float, float]]:
        """
        Returns the translation in (x,y,z) in meter compared to the last present instance based on keypoint matches
        and difference in distance
        """
        if len(self.occurrences) >= 2 and self.is_present():
            current_instance = self.get_current_instance()
            previous_instance = self.get_previous_present_instance()

            if current_instance is not None and current_instance.descriptors is not None and previous_instance is not None and previous_instance.descriptors is not None:
                matches = get_matches(current_instance.descriptors, previous_instance.descriptors)
                if matches:  # one or more matches
                    cumulative_2d_translation_in_px = (0, 0)
                    for match in matches:
                        kp_idx_current = match.queryIdx
                        kp_idx_last = match.trainIdx
                        key_point_current = current_instance.keypoints[kp_idx_current].pt
                        key_point_last = previous_instance.keypoints[kp_idx_last].pt
                        translation = tuple(map(operator.sub, key_point_current, key_point_last))  # subtract current point from last one
                        cumulative_2d_translation_in_px = tuple(map(operator.add, cumulative_2d_translation_in_px, translation))  # add them up
                    average_2d_translation_in_px = tuple(map(lambda e: e / len(matches), cumulative_2d_translation_in_px))  # div by length

                    current_distance = current_instance.approximate_distance()
                    previous_distance = previous_instance.approximate_distance()
                    z = current_distance - previous_distance

                    x, y = tuple(map(lambda px: self._pixel_to_meter(px, previous_distance + 0.5 * z), average_2d_translation_in_px))  # div by lensFactor to get real world measurements

                    return x, y, z

    def _pixel_to_meter(self, pixel: float, at_distance: float) -> float:
        """
        Calculates for a given number of pixels to how many meters they correspond at a given distance.
        """
        pixel_per_meter_at_1_m = 100 * CAMERA_TYPE.value[0] * VIDEO_SCALE
        pixel_per_meter_at_distance = pixel_per_meter_at_1_m / at_distance
        meter = pixel / pixel_per_meter_at_distance
        return meter

    def get_2d_trajectory(self, over_n_instances: int = 5) -> Optional[Tuple[float, float]]:
        """
        Returns tuple (x,y) of how the object (or rather its matched keypoints) moved on average over the last n frames
        """
        if len(self.occurrences) >= 2:
            last_n_instances = list(reversed(self.occurrences[-over_n_instances:]))
            smoothed_translation = (0.0, 0.0)
            for i in range(len(last_n_instances) - 1):
                current = last_n_instances[i]
                last = last_n_instances[i + 1]

                cumulative_translation = (0, 0)
                if current is not None and current.descriptors is not None and last is not None and last.descriptors is not None:
                    matches = get_matches(current.descriptors, last.descriptors)
                    if matches:  # one or more matches
                        for match in matches:
                            kp_idx_current = match.queryIdx
                            kp_idx_last = match.trainIdx
                            key_point_current = current.keypoints[kp_idx_current].pt
                            key_point_last = last.keypoints[kp_idx_last].pt
                            translation = tuple(map(operator.sub, key_point_current, key_point_last))  # subtract current point from last one
                            cumulative_translation = tuple(map(operator.add, cumulative_translation, translation))  # add them up
                        cumulative_translation = tuple(map(lambda x: x / len(matches), cumulative_translation))  # div by length

                decayed_translation = tuple(map(lambda x: x / (i + 1), cumulative_translation))  # decay: less impact for older instances
                smoothed_translation = tuple(map(operator.add, smoothed_translation, decayed_translation))  # add them up

            smoothed_translation = tuple(map(lambda x: x / over_n_instances, smoothed_translation))  # div by over_n_instances
            return smoothed_translation

    def __str__(self):
        return (
            f"{len(self.occurrences)} occurrences, "
            f"current instance: {self.get_current_instance()}, "
            f"present in last 5 frames: {self.was_present_in_last_n_frames(5)}, "
            f"next predicted pos: {self.get_next_position_prediction()}, "
            f"pos uncertainty: {self.get_next_position_uncertainty()},"
            f"trajectory: {self.get_2d_trajectory()}"
        )
