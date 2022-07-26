"""
Class used to compare the output of the system with the ground truth in the KITTI dataset
See: http://www.cvlibs.net/datasets/kitti/eval_object.php?obj_benchmark=3d
More details in the thesis
"""

import os

import pandas as pd

from data_model.DetectedObjects import DetectedObjects


def read_kitti_label_file(frame: str):
    path = f"data/imageSet/kitti/1000/{frame}.txt"
    full_path = os.path.abspath(path)
    df_labels = pd.read_csv(
        full_path,
        delim_whitespace=True,
        names=[
            "type",
            "truncated",
            "occluded",
            "alpha",
            "bbox_left",
            "bbox_top",
            "bbox_right",
            "bbox_bottom",
            "dimensions_height",
            "dimensions_width",
            "dimensions_length",
            "location_x",
            "location_y",
            "location_z",
            "rotation_y",
        ],
    )
    df_labels_clean = df_labels.drop(["DontCare"], errors="ignore")
    df_labels_clean["location_y"] = df_labels_clean["location_y"] - df_labels_clean["dimensions_height"] / 2  # y seems to be set to bottom of object in kitti dataset for some reason
    del df_labels_clean["truncated"]
    del df_labels_clean["occluded"]
    del df_labels_clean["alpha"]
    del df_labels_clean["dimensions_height"]
    del df_labels_clean["dimensions_width"]
    del df_labels_clean["dimensions_length"]
    del df_labels_clean["rotation_y"]
    return df_labels_clean


def detected_objects_to_data_frame(detected_objects: DetectedObjects):
    df_detected_objects = pd.DataFrame(columns=["type", "bbox_left", "bbox_top", "bbox_right", "bbox_bottom", "location_x", "location_y", "location_z"])
    for obj_track in detected_objects.objects.values():
        type = obj_track.class_name
        instance = obj_track.get_current_instance()
        bbox_left = instance.roi.x1
        bbox_top = instance.roi.y1
        bbox_right = instance.roi.x2
        bbox_bottom = instance.roi.y2
        location_x, location_y, location_z = instance.get_3d_position()
        data = pd.DataFrame(
            {
                "type": type,
                "bbox_left": bbox_left,
                "bbox_top": bbox_top,
                "bbox_right": bbox_right,
                "bbox_bottom": bbox_bottom,
                "location_x": location_x,
                "location_y": location_y,
                "location_z": location_z,
            },
            index=["type"],
        )
        df_detected_objects = df_detected_objects.append(data, ignore_index=True)
    return df_detected_objects


def classses_match(my_obj, kitti_obj) -> bool:
    my_type = my_obj["type"]
    kitti_type = kitti_obj["type"]
    if (
        (my_type == "person" and kitti_type == "Pedestrian")
        or (my_type == "car" and kitti_type == "Car")
        or (my_type == "car" and kitti_type == "Van")
        or (my_type == "truck" and kitti_type == "Truck")
        or (my_type == "train" and kitti_type == "Tram")
    ):
        # Classes match!
        return True
    else:
        return False


def compute_iou(my_obj, kitti_obj):
    my_x1 = my_obj["bbox_left"]
    my_y1 = my_obj["bbox_top"]
    my_x2 = my_obj["bbox_right"]
    my_y2 = my_obj["bbox_bottom"]
    my_box = (my_x1, my_y1, my_x2, my_y2)

    kitti_x1 = kitti_obj["bbox_left"]
    kitti_y1 = kitti_obj["bbox_top"]
    kitti_x2 = kitti_obj["bbox_right"]
    kitti_y2 = kitti_obj["bbox_bottom"]
    kitti_box = (kitti_x1, kitti_y1, kitti_x2, kitti_y2)

    iou = _intersection_over_union(my_box, kitti_box)
    return iou


def _intersection_over_union(boxA, boxB):
    # Expects boxes of type (x1, y1, x2, y2)
    # determine the (x, y)-coordinates of the intersection rectangle
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])
    # compute the area of intersection rectangle
    interArea = max(0, xB - xA + 1) * max(0, yB - yA + 1)
    # compute the area of both the prediction and ground-truth
    # rectangles
    boxAArea = (boxA[2] - boxA[0] + 1) * (boxA[3] - boxA[1] + 1)
    boxBArea = (boxB[2] - boxB[0] + 1) * (boxB[3] - boxB[1] + 1)
    # compute the intersection over union by taking the intersection
    # area and dividing it by the sum of prediction + ground-truth
    # areas - the intersection area
    iou = interArea / float(boxAArea + boxBArea - interArea)
    # return the intersection over union value
    return iou


def pad_with_zeros(number: int):
    return f"{number:06}"


class KittiEvaluator:
    df_combined_results = pd.DataFrame(columns=["frame", "iou", "my_type", "kitti_type", "my_x", "my_y", "my_z", "kitti_x", "kitti_y", "kitti_z"])
    kitti_objects_counter_total = 0
    kitti_objects_counter_matched = 0

    def compute_result(self, frame_number: int, detected_objects: DetectedObjects):
        frame_number_padded = pad_with_zeros(frame_number)
        df_kitti_objects = read_kitti_label_file(frame_number_padded)
        df_detected_objects = detected_objects_to_data_frame(detected_objects)

        for _, kitti_obj in df_kitti_objects.iterrows():
            self.kitti_objects_counter_total += 1
            for _, my_obj in df_detected_objects.iterrows():
                if classses_match(my_obj, kitti_obj):
                    iou = compute_iou(my_obj, kitti_obj)
                    if iou > 0.8:
                        my_type = my_obj["type"]
                        my_x = round(my_obj["location_x"], 2)
                        my_y = round(my_obj["location_y"], 2)
                        my_z = round(my_obj["location_z"], 2)

                        kitti_type = kitti_obj["type"]
                        kitti_x = kitti_obj["location_x"]
                        kitti_y = -kitti_obj["location_y"]  # Kitti's y axis points down, mine points up
                        kitti_z = kitti_obj["location_z"]

                        data = pd.DataFrame(
                            {
                                "frame": frame_number,
                                "iou": iou,
                                "my_type": my_type,
                                "kitti_type": kitti_type,
                                "my_x": my_x,
                                "my_y": my_y,
                                "my_z": my_z,
                                "kitti_x": kitti_x,
                                "kitti_y": kitti_y,
                                "kitti_z": kitti_z,
                            },
                            index=["frame"],
                        )
                        print(f"Frame: {frame_number} type: {my_type} iou: {iou:.2f}")
                        self.df_combined_results = self.df_combined_results.append(data, ignore_index=True)
                        self.kitti_objects_counter_matched += 1

    def write_results_as_csv(self):
        self.df_combined_results.to_csv("export/csv_export/kitti_evaluation_results.csv", sep=",")
        print(f"{self.kitti_objects_counter_matched}/{self.kitti_objects_counter_total} kitti objects matched, that is {self.kitti_objects_counter_matched / self.kitti_objects_counter_total * 100:.2f}%")


if __name__ == "__main__":
    read_kitti_label_file(pad_with_zeros(0))
