import cv2 as cv
import os

os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;udp"
vcap = cv.VideoCapture("rtsp://192.168.42.1/live", cv.CAP_FFMPEG)

while(1):
    ret, frame = vcap.read()
    cv.imshow('VIDEO', frame)
    cv.waitKey(1)
