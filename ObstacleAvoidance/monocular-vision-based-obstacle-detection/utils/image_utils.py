"""Miscellaneous utility functions for working with images"""
import glob
import os

import cv2 as cv2
from cv2 import VideoWriter
from moviepy.video.io.VideoFileClip import VideoFileClip

from Constants import InputDataType, CAMERA_TYPE
from camera_calibration.CameraCalibration import CameraCalibration


def letterbox_image(image, desired_size):
    """resize image with unchanged aspect ratio using padding (width, height)"""

    ih, iw = image.shape[:2]
    w, h = desired_size
    scale = min(w / iw, h / ih)
    nw = int(iw * scale)
    nh = int(ih * scale)

    resized_image = cv2.resize(image, (nw, nh))

    delta_w = w - nw
    delta_h = h - nh
    top, bottom = delta_h // 2, delta_h - (delta_h // 2)
    left, right = delta_w // 2, delta_w - (delta_w // 2)

    color = [128, 128, 128]
    new_image = cv2.copyMakeBorder(resized_image, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)
    return new_image


def take_center_square(image):
    """take the center square of the original image and returns it"""

    height, width = image.shape[:2]
    min_dimension = min(height, width)
    center = (width / 2, height / 2)

    square_center_image = cv2.getRectSubPix(image, (min_dimension, min_dimension), center)

    return square_center_image


def resize_image(image, desired_size):
    """resize image to desired size (width, height)"""

    resized_image = cv2.resize(image, desired_size)

    return resized_image


def get_image_patch_from_rect(image, rect):
    """Returns the specified area from the image"""
    top, left, bottom, right = rect
    size = (right - left, bottom - top)
    center = (left + size[0] / 2, top + size[1] / 2)
    return cv2.getRectSubPix(image, size, center)


def get_image_patch_from_contour(image, contour):
    """Returns the specified area from the image"""
    x, y, w, h = cv2.boundingRect(contour)
    size = (int(w * 1.2), int(h * 1.5))
    center = (x + w / 2, y + h / 2)
    return cv2.getRectSubPix(image, size, center)


def show(image, label="image", await_keypress=True):
    """Displays the image (optionally with a label) and halts the program until any key is pressed"""
    cv2.imshow(label, image)
    cv2.waitKey() if await_keypress else cv2.waitKey(1)


async def save_debug_image(image, filename, folder=None, resize_to=None):
    """
    Saves a given image under a specified filename.
    Optionally within a folder and resizing it (width, height)
    """
    if resize_to is not None:
        image = cv2.resize(image, resize_to)
    if folder:
        path = "export/debugImages/" + folder + "/" + filename + ".png"
    else:
        path = "export/debugImages/" + filename + ".png"
    cv2.imwrite(path, image)


def get_frames(input_type, path, from_sec_or_image=0, to_sec_or_image=None, undistort=False):
    """
    Retrieves frames from a video or directory in form of a generator.
    :param input_type: May be video or directory of images
    :param path: path to video or images
    :param from_sec_or_image: first frame
    :param to_sec_or_image: last frame
    :param undistort: images should be undistorted before being returned
    :return: a frame in a yielding fashion
    """
    if input_type == InputDataType.VIDEO:
        return get_frames_from_video(path, from_sec_or_image, to_sec_or_image, undistort)
    elif input_type == InputDataType.IMAGE:
        return get_frames_from_image_directory(path, from_image=from_sec_or_image, to_image=to_sec_or_image, undistort=undistort)
    else:
        raise Exception("Unknown input_type")


def get_frames_from_video(path_to_video, from_sec=0, to_sec=None, undistort=False):
    """
    Generator that reads a video file from disk and yields a color correct frame at a time
    """
    camera_calibration = CameraCalibration(CAMERA_TYPE)

    fullpath = os.path.abspath(path_to_video)
    video = VideoFileClip(fullpath, audio=False).subclip(from_sec, to_sec)
    for frame in video.iter_frames():
        # We have to switch the order of channels as opencv has a different order as they are coming from the camera
        color_corrected_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        if undistort:
            color_corrected_frame = camera_calibration.undistort(color_corrected_frame)
        yield color_corrected_frame


def get_frames_from_image_directory(path, image_types=None, from_image=0, to_image=None, undistort=False):
    """
    Generator that reads a directory of images from disk and yields a image at a time
    """
    camera_calibration = CameraCalibration(CAMERA_TYPE)

    if image_types is None:
        image_types = ["png", "jpg"]
    full_path_to_dir = os.path.abspath(path)
    image_paths = []
    for image_type in image_types:
        image_paths.extend(glob.glob(os.path.join(full_path_to_dir, "*." + image_type)))
    image_paths.sort()
    for image_path in image_paths[from_image:to_image]:
        image = cv2.imread(image_path)
        if undistort:
            image = camera_calibration.undistort(image)
        yield image


def draw_rectangle(image, box, color=(0, 0, 255), thickness=2, offset=(0, 0)):
    """
    Draws a rectangle on the provided image
    :param image: Image to draw on
    :param box: Box specifying the upper left and lower right corner of the rectangle
    :param color: Color of the rectangle
    :param thickness: Thickness of the border
    :param offset: Offset towards the upper left corner of the image
    """
    top, left, bottom, right = [int(x) for x in box]
    offset_y, offset_x = [int(x) for x in offset]

    left += offset_x
    right += offset_x
    top += offset_y
    bottom += offset_y

    cv2.rectangle(image, (left, top), (right, bottom), color, thickness)


def prepare_video_output(input_path, matcher_type, from_sec_or_image, to_sec_or_image, fps, input_dimensions) -> VideoWriter:
    """
    Prepares the VideoWriter and creates the video file with the parameters as part of the name so that it can be
    easily distinguished.
    """
    output_identifier = input_path.split("/")[-1]  # Get just last part of the path
    output_identifier = output_identifier.replace(".", "_")
    output_file_path = f"export/video/out_{output_identifier}_{matcher_type}_{from_sec_or_image}_to_{to_sec_or_image}.mov"
    video_writer = cv2.VideoWriter(output_file_path, cv2.VideoWriter_fourcc("X", "V", "I", "D"), fps, input_dimensions)
    return video_writer
