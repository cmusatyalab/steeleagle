from typing import Dict

from data_model.ObjectTrack import ObjectTrack

SAMENESS_THRESHOLD = 0.3  # 0 = match all, 1 match basically none
KEEP_TRACK_OF_OBJS_FOR_N_FRAMES = 5


class DetectedObjects:
    """
    Class storing the state of detected objects
    """

    def __init__(self):
        self.nextObjectID = 0
        self.objects: Dict[int, ObjectTrack] = dict()

    def get_next_id(self) -> int:
        """
        Just counts up starting from 1 to give every object a unique id
        :return: next object id
        """
        self.nextObjectID += 1
        return self.nextObjectID

    def get_active_object_tracks(self) -> Dict[int, ObjectTrack]:
        """
        :returns object tracks which are marked as active,
        meaning a corresponding object has been found in the last 5 frames.
        """
        return {key: track for key, track in self.objects.items() if track.active}

    def add_objects(self, new_objects):
        """
        Adds objects found in the current frame to the detected objects.
        Objects will be added to existing object tracks if found before or a new one will be initialized if the
        object has been found for the first time.
        Object tracks that were not updated will be marked as such and deactivated if too old.
        """
        touched_object_ids = set()
        for new_obj in new_objects:
            new_or_added_to_obj_id = self._add_object(new_obj, touched_object_ids)
            touched_object_ids.add(new_or_added_to_obj_id)

        # add None to all obj_tracks that have not found a new instance
        for obj_id, obj_track in self.get_active_object_tracks().items():
            if obj_id not in touched_object_ids:
                obj_track.add_occurrence(None)

        self._deactivate_old_object_tracks()

    def _add_object(self, new_obj_instance, already_touched_obj_ids, verbose=False):
        """
        Adds objects found in the current frame to the detected objects.
        Objects will be added to existing object tracks if found before or a new one will be initialized if the
        object has been found for the first time.
        Objects with id in already_touched_obj_ids will be skipped.
        """
        if verbose:
            print(f"\nNew Object: {new_obj_instance.class_name}, {new_obj_instance.roi}")

        obj_id_with_sufficient_similarity = self._find_existing_matching_obj_track(already_touched_obj_ids, new_obj_instance)

        if obj_id_with_sufficient_similarity:
            # Add to existing object
            obj_with_highest_similarity = self.objects[obj_id_with_sufficient_similarity]
            obj_with_highest_similarity.add_occurrence(new_obj_instance)
            return obj_id_with_sufficient_similarity
        else:
            # Add as new object
            new_obj_track = ObjectTrack(new_obj_instance)
            new_obj_id = self.get_next_id()
            self.objects[new_obj_id] = new_obj_track
            return new_obj_id

    def _find_existing_matching_obj_track(self, already_touched_obj_ids, new_obj_instance):
        """
        Find object id of object that most closely matches new_obj_instance while not being in already_touched_obj_ids
        """
        obj_id_with_sufficient_similarity = None
        highest_similarity = 0
        for obj_id, obj_track in self.get_active_object_tracks().items():
            if obj_id not in already_touched_obj_ids:
                similarity_to_current_obj = obj_track.similarity_to(new_obj_instance, over_n_instances=KEEP_TRACK_OF_OBJS_FOR_N_FRAMES)
                if similarity_to_current_obj > highest_similarity:
                    highest_similarity = similarity_to_current_obj
                    if similarity_to_current_obj > SAMENESS_THRESHOLD:
                        obj_id_with_sufficient_similarity = obj_id
        return obj_id_with_sufficient_similarity

    def _deactivate_old_object_tracks(self):
        """
        Marks objects as deactivated if the object hasn't been found in KEEP_TRACK_OF_OBJS_FOR_N_FRAMES frames
        """
        obj_tracks_to_deactivate = [obj_track for key, obj_track in self.get_active_object_tracks().items() if not obj_track.was_present_in_last_n_frames(KEEP_TRACK_OF_OBJS_FOR_N_FRAMES)]
        for track in obj_tracks_to_deactivate:
            track.active = False
