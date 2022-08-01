"""Miscellaneous utility functions for exporting data"""

import csv
from typing import Optional

from data_model.DetectedObjects import DetectedObjects
from data_model.ObjectInstance import ObjectInstance


def write_detected_objects_to_csv(detected_objects: DetectedObjects, prefix=""):
    """
    Writes data collected about the detected_objects to disc in csv format, prefixed by 'prefix'
    """
    for ot_id, ot in detected_objects.objects.items():
        file = open("export/csv_export/" + prefix + "_" + ot.class_name + "_" + str(ot_id) + ".csv", "w")
        with file:
            writer = csv.writer(file)
            header = ["index", "id", "class_name", "present", "confidence", "speed (km/h)", "velocity (m/s)", "roi_center", "distance", "3d_position", "# keypoints"]
            writer.writerow(header)
            occurrences: [Optional[ObjectInstance]] = ot.occurrences

            for index, occ in enumerate(occurrences):
                row = [
                    index,
                    ot_id,
                    ot.class_name,
                    ot.is_present(),
                    "-" if occ is None else occ.confidence_score,
                    "-" if occ is None else occ.speed,
                    "-" if occ is None else occ.velocity,
                    "-" if occ is None else [occ.roi.get_center()],
                    "-" if occ is None else occ.approximate_distance(),
                    "-" if occ is None else tuple(map(lambda e: round(e, 2), occ.get_3d_position())),
                    "-" if occ is None or occ.keypoints is None else len(occ.keypoints),
                ]
                writer.writerow(row)
