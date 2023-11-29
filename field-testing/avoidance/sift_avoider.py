#!/usr/bin/env python

# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import olympe
from olympe.messages.ardrone3.Piloting import PCMD
from olympe.messages.ardrone3.PilotingState import GpsLocationChanged
import cv2
import numpy as np
import logging
from collections import OrderedDict
import time,sys
from matplotlib import pyplot as plt
import sys
sys.path.append('./avoidance/')
from common import *
import operator as op
import math
import threading
import zmq
import time
import traceback
from datetime import datetime

STREAM_FPS = 1 #used for ttc
RATIO = 0.75
AGE = 10

FOLDER = "./avoidance/old-traces/"

def ClusterKeypoints(keypoints, img, epsilon=0):
    if len(keypoints) < 2: return []

    cluster = []
    unclusteredKPs = sorted(keypoints,key=op.attrgetter('pt'))
    while unclusteredKPs:
        clust = [unclusteredKPs.pop(0)]
        kp = clust[0]
        i = 0
        while i < len(unclusteredKPs):
            if overlap(kp, unclusteredKPs[i], eps=epsilon):
                clust.append(unclusteredKPs.pop(i))
            else:
                i += 1
        if (len(clust) >= 3): cluster.append(Cluster(clust,img))

    return cluster

def mse(img1, img2):
   h, w = img1.shape
   diff = cv2.subtract(img1, img2)
   err = np.sum(diff**2)
   mse = err/(float(h*w))
   return mse

class SIFTAvoider(threading.Thread):
    def __init__(self, drone, contrast=0.04, edge=50, dist=200.0, scale=1.3, roi=3, eps=50, speed=5):
        self.drone = drone
        self.c = contrast
        self.e = edge
        self.d = dist
        self.s = scale
        self.r = roi
        self.roi = None
        self.eps = eps
        self.speed = speed

        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.SUB)
        self.socket.connect('tcp://localhost:5555')
        self.socket.setsockopt(zmq.SUBSCRIBE, b'')

        self.image_size = (640, 480)
        self.image = None
        self.prev_image = None

        output_frames = []

        self.init_sift()
        super().__init__()
    
    def execute_PCMD(self, dpitch, droll):
        print(f"ROLL: {droll}, PITCH: {dpitch}")
        self.drone(PCMD(1, round(droll), round(dpitch), 0, 0, timestampAndSeqNum=0))

    def move_by_offsets(self, vec):
        offset_from_center = self.image_size[0] / 2
        normalized_vec = max(-1.0, min(vec / offset_from_center, 1.0))
        actuation = max(-100, min(normalized_vec * 30, 100))
        self.execute_PCMD(self.speed, actuation)

    def recv_array(self, flags=zmq.NOBLOCK, copy=True, track=False):
        """recv a numpy array"""
        md = self.socket.recv_json(flags=flags)
        msg = self.socket.recv(flags=flags, copy=copy, track=track)
        buf = memoryview(msg)
        A = np.frombuffer(buf, dtype=md['dtype'])
        return A.reshape(md['shape'])

    def run(self):
        self.tracking = False
        self.active = True

        trace = open(FOLDER + datetime.now().strftime("%m-%d-%Y-%H-%M-%S") + ".txt", 'a')

        lastvec = 0
        while self.active:
            gps = self.drone.get_state(GpsLocationChanged)
            lat = gps["latitude"]
            lng = gps["longitude"]
            trace.write(f"{lat}, {lng}" + '\n')
            try:
                self.image = self.recv_array()
                vec = self.get_offsets()
                print(f"Got vector back from offsets: {vec}")
                lastvec = vec
                self.prev_image = self.image
                if vec is not None:
                    self.move_by_offsets(vec)
            except Exception as e:
                if lastvec:
                    self.move_by_offsets(lastvec)
            time.sleep(0.05)

        trace.close()

    def stop(self):
        self.active = False
        self.tracking = False
        self.first_image = False
        cv2.destroyAllWindows()

    def init_sift(self):
        print("Init SIFT.")
        self.bfmatcher = cv2.BFMatcher(cv2.NORM_L2)
        self.sift = cv2.SIFT_create(nfeatures=0, contrastThreshold=self.c, edgeThreshold=self.e)
        self.first_image = True
        self.id = 1

        try:
            self.roi = np.zeros(prev_img.shape,np.uint8)
            scrapY, scrapX = prev_img.shape[0]//self.r, prev_img.shape[1]//(self.r + 1)
            self.roi[scrapY:-scrapY, scrapX:-scrapX] = True
        except Exception as e:
            pass

    def match(self):
        print("Filtering matches.")
        train_indices_matched = []
        prev_kps_not_matched = []
        prev_descs_not_matched = []

        matches = self.bfmatcher.match(self.descs, self.prev_descs)
        # Sort them in the order of their distance.
        ## find the list of kps that were not matched.

        matches = sorted(matches, key = lambda x:x.distance)

        # Filter out bad matches
        good = []
        for m in matches:
            if m.distance < self.d:
                good.append(m)
                train_indices_matched.append(m.trainIdx)
        for each_prev_kp_index in range(len(self.prev_kps)):
            if  each_prev_kp_index not in train_indices_matched:
                prev_kps_not_matched.append(self.prev_kps[each_prev_kp_index])
                prev_descs_not_matched.append(self.prev_descs[each_prev_kp_index])

        if(len(matches) > 0):
            max_value = max(matches, key=lambda x : x.distance)
            min_value = min(matches, key=lambda x : x.distance)

        return good

    def cull(self, good, curr, prev):
        print("Culling matches!")
        bigger = []
        expandingKPs = []

        kps, descs, img = curr
        prev_kps, prev_descs, prev_img = prev

        for g in good:
            clsid = prev_kps[g.trainIdx].class_id
            curr_point_x, curr_point_y = int(np.round(kps[g.queryIdx].pt[0])), int(np.round(kps[g.queryIdx].pt[1]))
            prev_point_x, prev_point_y = int(np.round(prev_kps[g.trainIdx].pt[0])), int(np.round(prev_kps[g.trainIdx].pt[1]))

            size_expansion = 1.5 ### MAKE THIS TUNABLE
            curr_size = int(max(1, np.round((kps[g.queryIdx].size)*size_expansion)))
            prev_size = int(max(1, np.round((prev_kps[g.trainIdx].size)*size_expansion)))
            if prev_size <= curr_size - 2:
                pass
            curr_total_x, curr_total_y = img.shape[1], img.shape[0]
            prev_total_x, prev_total_y = prev_img.shape[1], prev_img.shape[0]
            if (curr_point_x + curr_size/2 + 1 > curr_total_x) or (curr_point_y + curr_size/2 + 1 > curr_total_y) or (prev_point_x + prev_size/2 + 1 > prev_total_x) or (prev_point_y + prev_size/2 + 1 > prev_total_y) or \
                    (curr_point_x - curr_size / 2 - 1 < 0) or (curr_point_y - curr_size / 2 - 1 < 0) or (prev_point_x - prev_size / 2 - 1 < 0) or (prev_point_y - prev_size / 2 - 1 < 0):
                continue
            if curr_size < prev_size + 2: continue


            # extract sub image from perev image
            ## new image borders
            if curr_size %2 == 1:
                left = int(curr_point_x - math.floor(curr_size/2))
                right = int(curr_point_x + math.ceil(curr_size/2))
                top = int(curr_point_y - math.floor(curr_size/2))
                bottom = int(curr_point_y + math.ceil(curr_size/2))
            else:
                left = int(curr_point_x - curr_size / 2)
                right = int(curr_point_x + curr_size / 2)
                top = int(curr_point_y - curr_size / 2)
                bottom = int(curr_point_y + curr_size / 2)

            temp_curr_image = np.asarray(img[top:bottom, left:right])

            if prev_size % 2 == 1:
                left = int(prev_point_x - math.floor(prev_size / 2))
                right = int(prev_point_x + math.ceil(prev_size / 2))
                top = int(prev_point_y - math.floor(prev_size / 2))
                bottom = int(prev_point_y + math.ceil(prev_size / 2))
            else:
                left = int(prev_point_x - prev_size / 2)
                right = int(prev_point_x + prev_size / 2)
                top = int(prev_point_y - prev_size / 2)
                bottom = int(prev_point_y + prev_size / 2)

            temp_prev_image = np.asarray(prev_img[top:bottom, left:right])

            ## loop from previous key point length to current key point length
            scale_results=np.empty(0)
            results_dict = {}
            for expansion in range(0, curr_size - prev_size, 2):
                cropped_temp_curr_image = temp_curr_image[expansion//2:curr_size - expansion//2, expansion//2:curr_size - expansion//2]
                resized_temp_prev_image = cv2.resize(temp_prev_image, (curr_size - expansion, curr_size - expansion))

                error = mse(cropped_temp_curr_image, resized_temp_prev_image)
                results_dict[error] = resized_temp_prev_image.shape[0]/temp_prev_image.shape[0]
            best = min(results_dict.keys())
            ratio = results_dict[best]


            if(ratio > self.s): ## changed the condition check for clustering
                bigger.append(g)
                expandingKPs.append(prev_kps[g.trainIdx])

        return bigger, expandingKPs


    def get_offsets(self):
        print("Getting offsets!")
        if self.first_image:
            print("First image.")
            img = cv2.cvtColor(self.image, cv2.COLOR_BGR2GRAY)
            self.prev_kps, self.prev_descs = self.sift.detectAndCompute(img, self.roi)
            for kp in self.prev_kps:
                kp.class_id = self.id
            self.id += 1
            feature_img = cv2.drawKeypoints(img, self.prev_kps, None, (0, 0, 255), 4)
            self.t_last = time.time()
            self.first_image = False
            return None
        else:
            print("Extracting kps.")
            self.t_curr = time.time()
            b_w_disp = self.image.copy()
            dispim = self.image.copy()
            img = cv2.cvtColor(self.image, cv2.COLOR_BGR2GRAY)
            self.kps, self.descs = self.sift.detectAndCompute(img, self.roi)
            for kp in self.kps:
                kp.class_id = self.id
            self.id += 1
            
            good = self.match()
            prev_gray = cv2.cvtColor(self.prev_image, cv2.COLOR_BGR2GRAY)
            b, expand = self.cull(good, (self.kps, self.descs, img), (self.prev_kps, self.prev_descs, prev_gray))

            print("Clustering.")
            cluster = ClusterKeypoints(expand, img, epsilon=self.eps)
            b_w_disp[0:b_w_disp.shape[0], 0:b_w_disp.shape[1]] = (255, 255, 255)
            for c in cluster:
                b_w_disp[0:img.shape[1], c.p0[0]:c.p1[0]] = (0,0,0)

            # Scrap out the ROI
            scrapY, scrapX = self.image_size[0]//self.r, self.image_size[1]//(self.r + 1)
            b_w_disp = b_w_disp[ scrapY : b_w_disp.shape[0] - scrapY,scrapX : b_w_disp.shape[1] - scrapX]
            b_w_disp = cv2.cvtColor(b_w_disp, cv2.COLOR_BGR2GRAY)

            # find contours in the binary image
            contours, h = cv2.findContours(b_w_disp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            try:
                c = max(contours, key=cv2.contourArea)
                # calculate moments for each contour
                M = cv2.moments(c)
                cX = int(M["m10"] / M["m00"])
                cY = int(M["m01"] / M["m00"])
                cv2.circle(dispim, (scrapX + cX, scrapY + cY), 5, (0, 255, 0), -1)
                cv2.putText(dispim, "safe", (scrapX + cX, scrapY + cY - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            except Exception as e:
                pass

            self.prev_img = self.image
            self.prev_kps = self.kps
            self.prev_descs = self.descs
            self.t_last = self.t_curr

            cv2.imshow("Safe", dispim)
            cv2.waitKey(1)
            return (scrapX + cX) - (self.image_size[0] / 2) 
