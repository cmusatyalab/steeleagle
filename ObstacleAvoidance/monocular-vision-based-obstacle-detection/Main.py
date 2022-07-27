"""
Main entrypoint
"""
import argparse
import asyncio

import Constants
from utils.timer import print_timing_results, timing


@timing
def process_video():
    """
    Processes the video defined in Constants.
    Saves frames for debugging, outputs video and saves results as csv.
    """
    output_video = prepare_video_output(Constants.INPUT_PATH, Constants.MATCHER_TYPE.value, Constants.FROM_SEC_OR_IMAGE, Constants.TO_SEC_OR_IMAGE, Constants.OUTPUT_FPS, Constants.INPUT_DIMENSIONS)
    detected_objects = DetectedObjects()

    for frame_number, frame in enumerate(get_frames(Constants.INPUT_DATA_TYPE, Constants.INPUT_PATH, Constants.FROM_SEC_OR_IMAGE, Constants.TO_SEC_OR_IMAGE, undistort=False)):
        result = detect(frame)

        newly_detected_objects = create_objects(result, frame)
        detected_objects.add_objects(newly_detected_objects)

        result_frame = visualize.draw_instances(frame, detected_objects)

        print(f"Frame {frame_number}: detected {len(newly_detected_objects)} objects. {len(detected_objects.objects)} total objects")
        show(result_frame, "Frame", await_keypress=False)
        asyncio.run(save_debug_image(result_frame, "frame_" + str(frame_number)))
        output_video.write(result_frame)

    output_video.release()
    write_detected_objects_to_csv(detected_objects, "test")


def main():
    """
    Main entry point.
    """
    process_video()
    print_timing_results()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process video")
    parser.add_argument(
        "input",
        type=str,
        help="Video file or directory of images to be processed"
    )
    parser.add_argument(
        "--from",
        dest="from_sec_or_image",
        type=int,
        default=0,
        help="From video second or image number"
    )
    parser.add_argument(
        "--to",
        dest="to_sec_or_image",
        type=int,
        default=None,
        help="To video second or image number"
    )
    parser.add_argument(
        "--inputType",
        dest="inputType",
        type=Constants.InputDataType,
        choices=list(Constants.InputDataType),
        default=Constants.InputDataType.VIDEO,
        help="Input type can be a VIDEO or a directory with IMAGEs",
    )
    parser.add_argument(
        "--inputDimensions",
        dest="inputDimensions",
        nargs=2,
        metavar=("x", "y"),
        type=int,
        help="Input dimensions for video or image series"
    )
    parser.add_argument(
        "--inputScale",
        dest="inputScale",
        type=float,
        default=1,
        help="Scale compared to original video (e.g. 0.5)"
    )
    parser.add_argument(
        "--matcherType",
        dest="matcherType",
        type=Constants.MatcherType,
        choices=list(Constants.MatcherType),
        default=Constants.MatcherType.ORB,
        help="Matcher type can be SIFT, SURF or ORB"
    )
    parser.add_argument(
        "--cameraType",
        dest="cameraType",
        type=Constants.CameraType,
        choices=list(Constants.CameraType),
        default=Constants.CameraType.IPHONE_XR_4K_60,
        help="Camera type can be IPHONE_XR_4K_60, IPHONE_8_PLUS_4K_60 or FL2_14S3C_C",
    )
    parser.add_argument(
        "--inputFps",
        dest="inputFps",
        type=int,
        default=60,
        help="Fps of input video"
    )
    parser.add_argument(
        "--outputFps",
        dest="outputFps",
        type=int,
        default=10,
        help="Fps for output video"
    )

    args = parser.parse_args()
    print(args)

    Constants.INPUT_PATH = args.input
    Constants.FROM_SEC_OR_IMAGE = args.from_sec_or_image
    Constants.TO_SEC_OR_IMAGE = args.to_sec_or_image
    Constants.INPUT_DATA_TYPE = args.inputType
    Constants.INPUT_DIMENSIONS = tuple(args.inputDimensions)
    Constants.VIDEO_SCALE = args.inputScale
    Constants.MATCHER_TYPE = args.matcherType
    Constants.CAMERA_TYPE = args.cameraType
    Constants.INPUT_FPS = args.inputFps
    Constants.OUTPUT_FPS = args.outputFps

    # Constants need to be set before imports so that they are taken into account
    from data_model.DetectedObjects import DetectedObjects
    from data_model.ObjectInstance import create_objects
    from mrcnn import visualize
    from mrcnn.Mask_R_CNN_COCO import detect
    from utils.image_utils import save_debug_image, show, prepare_video_output, get_frames
    from utils.export_utils import write_detected_objects_to_csv

    main()
