import olympe
from olympe.messages.thermal import set_mode, set_rendering
import cv2 as cv
import os

drone = olympe.Drone('192.168.42.1')
drone.connect()
drone(set_mode(mode="blended")).wait().success()

os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;udp"
vcap = cv.VideoCapture("rtsp://192.168.42.1/live", cv.CAP_FFMPEG)

while(1):
    ret, frame = vcap.read()
    cv.imshow('VIDEO', frame)
    cv.waitKey(1)
