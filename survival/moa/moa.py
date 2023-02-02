#!/usr/bin/env python
import argparse
import cv2
import numpy as np
import logging
from collections import OrderedDict
import time,sys
from matplotlib import pyplot as plt

STREAM_FPS = 1 #used for ttc
RATIO = 0.75

class KeyPoint(object):
     def __init__(self):
        self.age = -1
        self.lastFrameIdx = 0
        self.detects = 0
        self.scalehist = []
        self.timehist = []
        self.keypoint = None
        self.descriptor = None
        self.consecutive = 0


logger = logging.getLogger(__name__)
logging.basicConfig()


 
parser = argparse.ArgumentParser(usage="moa.py [options]")

#SIFT Params
parser.add_argument("-c", "--contrast-threshold", type=float, default=0.04
                  , help="Set the contrast threshold for SIFT. (default=0.04)")

parser.add_argument("-e", "--edge-threshold", type=float, default=10
                  , help="Set the edge threshold for SIFT. (default=10)")
#Matching Params
parser.add_argument("-d", "--distance", type=float, default=200.0
                  , help="Distance (in pixels?) of each keypoint match. (default=200.0)")

parser.add_argument("-s", "--scale", type=float, default=1.2
                  , help="Scale at which we filter keypoints that are getting larger. (default=1.2)")

parser.add_argument("--roi", type=int, default=4
                  , help="Factor for computing the region of interest (default=4).")

parser.add_argument("-l", "--logging", type=int, default=20, 
                    help="Log level (DEBUG=10, INFO=20, WARNING=30, ERROR=40, CRITICAL=50) [default: 20]")

parser.add_argument("--video-file", default=None
                    , help="Load a video file to test.")

parser.add_argument("--sleep",  type=int, default=1000, help="Sleep with waitKey for this many ms (default=1000).")

opts = parser.parse_args()
logger.setLevel(opts.logging)

cv2.namedWindow("SIFT", flags=cv2.WINDOW_NORMAL)
cv2.namedWindow("MATCHES", flags=cv2.WINDOW_NORMAL)



capture = cv2.VideoCapture(opts.video_file)
ret, prev_img = capture.read()
if not ret: 
    logger.error(f"Failed to read from VideoCapture: {ret}")
#convert to greyscale
prev_img = cv2.cvtColor(prev_img,cv2.COLOR_BGR2GRAY)

bfmatcher = cv2.BFMatcher(cv2.NORM_L2)
sift = cv2.SIFT_create(contrastThreshold=opts.contrast_threshold, edgeThreshold=opts.edge_threshold)
id = 1
# mask out region of interest
try:
    roi = np.zeros(prev_img.shape,np.uint8)
    scrapY, scrapX = prev_img.shape[0]//opts.roi, prev_img.shape[1]//opts.roi
    roi[scrapY:-scrapY, scrapX:-scrapX] = True
except Exception as e:
    logger.error(e)
    

# get keypoints and feature descriptors
prev_kps, prev_descs = sift.detectAndCompute(prev_img,roi)
for kp in prev_kps: 
    kp.class_id = id
id += 1

feature_img = cv2.drawKeypoints(prev_img, prev_kps, None,(0,0,255),4)
cv2.imshow("SIFT", feature_img)
cv2.waitKey(1)

while True:
    ret, img = capture.read()
    if not ret:
        logger.error(f"Failed to read frame from capture device.")
        break
    else:
        logger.info(f"Frame #{id}")
        #convert to greyscale
        img = cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
        # get keypoints and feature descriptors
        kps, descs = sift.detectAndCompute(img,roi)
        for kp in kps: 
            kp.class_id = id
            logger.debug(f"")
        id += 1
        feature_img = cv2.drawKeypoints(img, kps, None,(0,0,255),4)
        cv2.rectangle(feature_img,(scrapX,scrapY),(feature_img.shape[1]-scrapX,feature_img.shape[0]-scrapY),(0,255,255),thickness=1)
        cv2.imshow("SIFT", feature_img)
        cv2.waitKey(1)

        #matches = bfmatcher.knnMatch(prev_descs, descs, k=2)
        matches = bfmatcher.match(descs,prev_descs)
        # Sort them in the order of their distance.
        matches = sorted(matches, key = lambda x:x.distance)
        logger.info(f"Total matches: {len(matches)}")

        # # Apply ratio test
        # good = []
        # for m,n in matches:
        #     print(f"M-dist: {m.distance}, N-dist: {n.distance}")
        #     if m.distance < RATIO*n.distance:
        #         good.append(m)
        # print(f"Good Matches (passed ratio test of  < {RATIO}): {len(good)}")

        # Filter out bad matches
        good = []
        for m in matches:
            logger.debug(f"M-dist: {m.distance}")
            if m.distance < opts.distance:
                good.append(m)
        max_value = max(matches, key=lambda x : x.distance)
        min_value = min(matches, key=lambda x : x.distance)
        logger.info(f"Min/Max dist: {min_value.distance} / {max_value.distance}")
        logger.info(f"Good Matches (distance < than {opts.distance}): {len(good)}")
        
        # Compare sizes of kps and eliminate all that are the same or getting smaller.
        bigger = []
        for g in good:
            logger.debug(f"Prev Size: {prev_kps[g.trainIdx].size}, Current Size: {kps[g.queryIdx].size}")
            if(kps[g.queryIdx].size > opts.scale*prev_kps[g.trainIdx].size):
                bigger.append(g)
        logger.info(f"Bigger Matches (curr.size > {opts.scale} * prev.size): {len(bigger)}")


        # cv.drawMatchesKnn expects list of lists as matches.
        matches_img = cv2.drawMatches(img,kps,prev_img,prev_kps,bigger,None,(128,128,0),(0,0,255),flags=cv2.DRAW_MATCHES_FLAGS_NOT_DRAW_SINGLE_POINTS|cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS)
        cv2.imshow("MATCHES", matches_img)
        cv2.waitKey(opts.sleep)

        prev_img = img
        prev_kps = kps
        prev_descs = descs

capture.release()
cv2.destroyAllWindows()

