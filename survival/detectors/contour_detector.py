import cv2
import numpy as np
from detectors.detector_base import DetectorBase

# --- Contour Detector ---
# Uses contours to find occupied space and directs the drone
# to fly to free space. Implemented according to the specification
# in https://hal-enac.archives.ouvertes.fr/hal-01705673/document

class ContourDetector(DetectorBase):

    # Blur kernel size
    K = (10, 10)

    def detect(self, frame):
        # Step 1: Convert frame from BGR to Gray color spectrum
        tmp = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Step 2: Blur the image
        tmp = cv2.blur(tmp, self.K)

        # Step 3: Detect edges using Canny Edge Detector
        high_thresh, thresh_im = cv2.threshold(tmp, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        low_thresh = 0.5*high_thresh
        tmp = cv2.Canny(tmp, low_thresh, high_thresh)

        # Step 4: Find contours
        contours, hierarchy = cv2.findContours(tmp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)

        # Step 5: Draw contours
        cv2.drawContours(frame, contours, -1, (0, 255, 0), 3)

        return frame


        
