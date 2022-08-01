import cv2
import numpy as np
from detectors.detector_base import DetectorBase
from matplotlib import pyplot as plt

# --- Color Segmentation and Particle Analysis ---

class ParticleAnalysis(DetectorBase):

    minArea = 1000
    # Reference to the previously captured frame.
    prevFrame = None
    # First run boolean
    first = True

    def detect(self, frame):
        disparity = frame
        if self.prevFrame is not None or self.first:
            if self.first:
                self.prevFrame = frame
                self.first = False
            stereo = cv2.StereoBM_create(numDisparities=16, blockSize=15)
            imgL = cv2.cvtColor(self.prevFrame, cv2.COLOR_BGR2GRAY)
            imgR = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            disparity = stereo.compute(imgL, imgR)
            self.prevFrame = frame

        # coloring bounding arrays
        lower_RGB = np.array([0,0,0])
        upper_RGB = np.array([85,85,85])

        # conduct color threshold
        mask = cv2.inRange(frame, lower_RGB, upper_RGB)

        # find contours
        cnts, heirarchy = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # loop over the contours
        for c in cnts:
            # if the contour is too small, ignore it
            if cv2.contourArea(c) < self.minArea:
                continue

            #compute bounding boxes and and draw on frame
            (x, y, w, h) = cv2.boundingRect(c)
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)

        cv2.imshow('Frame', frame)
        cv2.imshow('Depth', np.square(disparity))
        cv2.waitKey(1)

        return frame
