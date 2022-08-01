"""
Code adapted from
https://opencv-python-tutroals.readthedocs.io/en/latest/py_tutorials/py_calib3d/py_calibration/py_calibration.html
"""

import glob

import cv2 as cv2
import numpy as np

import Constants
from utils.timer import timing


class CameraCalibration:
    """
    Class used to get rid of distortion in images. It needs a calculated calibration matrix for each new camera model.
    """

    def __init__(self, camera_type: Constants.CameraType):
        path_to_calibration_file = f"camera_calibration/camera_calibration_{camera_type.name}.npz"
        # Scale to image size
        camera_matrix, self.distortion_coeffs, camera_matrix_with_crop = load_calibration_data(path_to_calibration_file)

        scaled_camera_matrix = camera_matrix * Constants.VIDEO_SCALE
        scaled_camera_matrix[2][2] = 1

        scaled_camera_matrix_with_crop = camera_matrix_with_crop * Constants.VIDEO_SCALE
        scaled_camera_matrix_with_crop[2][2] = 1

        self.camera_matrix = scaled_camera_matrix
        self.camera_matrix_with_crop = scaled_camera_matrix_with_crop

    @timing
    def undistort(self, image):
        return cv2.undistort(image, self.camera_matrix, self.distortion_coeffs, None, self.camera_matrix_with_crop)


def calculate_camera_matrix_and_distortion_coefficients(camera_model_name):
    # termination criteria
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

    # prepare object points, like (0,0,0), (1,0,0), (2,0,0) ....,(7,5,0)
    object_points = np.zeros((6 * 8, 3), np.float32)
    object_points[:, :2] = np.mgrid[0:8, 0:6].T.reshape(-1, 2)

    # Arrays to store object points and image points from all the images.
    real_world_points = []  # 3d point in real world space
    image_points = []  # 2d points in image plane.

    image_paths = glob.glob("calibration_images/*.png")

    for path_to_image in image_paths:
        img = cv2.imread(path_to_image)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Find the chess board corners
        chess_board_successfully_detected, corners = cv2.findChessboardCorners(gray, (8, 6), None)
        print("Found chess board in: " + path_to_image + " : " + str(chess_board_successfully_detected))

        # If found, add object points, image points (after refining them)
        if chess_board_successfully_detected:
            real_world_points.append(object_points)

            refined_corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
            image_points.append(refined_corners)

            # Draw and display the corners
            # img = cv2.drawChessboardCorners(img, (7, 6), refined_corners, chess_board_successfully_detected)
            # cv2.imshow('img', resize_image(img, (1920, 1080)))
            # cv2.waitKey()

    cv2.destroyAllWindows()

    ret, camera_matrix, distortion_coeffs, rvecs, tvecs = cv2.calibrateCamera(real_world_points, image_points, gray.shape[::-1], None, None)

    h, w = gray.shape[:2]
    camera_matrix_with_crop, roi = cv2.getOptimalNewCameraMatrix(camera_matrix, distortion_coeffs, (w, h), 1, (w, h))

    file_name = f"camera_calibration_{camera_model_name}.npz"
    np.savez(file_name, camera_matrix=camera_matrix, distortion_coeffs=distortion_coeffs, camera_matrix_with_crop=camera_matrix_with_crop)


def load_calibration_data(path_to_camera_model_file):
    data = np.load(path_to_camera_model_file)
    camera_matrix = data["camera_matrix"]
    distortion_coeffs = data["distortion_coeffs"]
    camera_matrix_with_crop = data["camera_matrix_with_crop"]
    return camera_matrix, distortion_coeffs, camera_matrix_with_crop


def undistort(image_path, camera_matrix, distortion_coeffs, camera_matrix_with_crop):
    from utils.image_utils import resize_image

    image = cv2.imread(image_path)
    cv2.imshow("distorted", resize_image(image, (1920, 1080)))
    cv2.waitKey()
    undistorted_image = cv2.undistort(image, camera_matrix, distortion_coeffs, None, camera_matrix_with_crop)
    cv2.imshow("undistorted", resize_image(undistorted_image, (1920, 1080)))
    cv2.waitKey()


# For local development/debugging
if __name__ == "__main__":
    # calculate_camera_matrix_and_distortion_coefficients("iPhoneXR_4k_60")
    camera_matrix, distortion_coeffs, camera_matrix_with_crop = load_calibration_data("camera_calibration_IPHONE_XR_4K_60.npz")
    undistort("calibration_images/vlcsnap-2019-06-10-14h49m29s009.png", camera_matrix, distortion_coeffs, camera_matrix_with_crop)
