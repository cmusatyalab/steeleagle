#!/usr/bin/env python

import cv2
import numpy as np
import scipy.stats as stats

from common import *
from framebuffer import VideoBuffer
import scale_matching as smatch

import operator as op
from collections import OrderedDict

import time,sys


TARGET_N_KP = 50
MIN_THRESH = 2000
MAX_THRESH = 2500
LAST_DAY = 10

VERBOSE = 1

gmain_win = "flownav"
gtemplate_win = "Template matching"


def ClusterKeypoints(keypoints,kphist,img):
    if len(keypoints) < 2: return []

    cluster = []
    unclusteredKPs = sorted(keypoints,key=op.attrgetter('pt'))
    while unclusteredKPs:
        clust = [unclusteredKPs.pop(0)]
        kp = clust[0]
        i = 0
        while i < len(unclusteredKPs):
            if overlap(kp,unclusteredKPs[i]):
                clust.append(unclusteredKPs.pop(i))
            else:
                i += 1
        if (len(clust) >= 2): cluster.append(Cluster(clust,img))

    return cluster


def uniqid_gen():
    uid = 2 # starts at 2 since default class_id for keypoints can be +/-1
    while(1):
        yield uid
        uid += 1

# ==========================================================
# process options and set up defaults
# ==========================================================
import argparse
import os
 
parser = argparse.ArgumentParser(usage="flownav.py [options]")

parser.add_argument("--threshold", dest="threshold", type=float, default=2000.
                  , help="Set the Hessian threshold for keypoint detection.")

parser.add_argument("-m", "--draw-matches", dest="showmatches"
                    , action="store_true", default=False
                    , help="Show scale matches for each expanding keypoint.")

parser.add_argument("--draw-tags", dest="drawtags", action="store_true", default=False
                    , help="Draw tags for individual expanding keypoints.")

parser.add_argument("-v", "--verbose", dest="verbose", action="count", default=1
                    , help="Print verbose output to stdout. Multiple v's for more verbosity.")

parser.add_argument("-q", "--quiet", dest="quiet", default=False, action='store_true'
                    , help="Quiet all output to stdout. (%(default)s)")

parser.add_argument("--no-draw", dest="nodraw", action="store_true", default=False
                    , help="Don't draw on display image. (true)")

parser.add_argument("--loop", dest="loop", action="store_true", default=False
                    , help="Loop video. (%(default)s)")

parser.add_argument("--video-file", dest="video", default=None
                    , help="Load a video file to test.")

parser.add_argument("-r","--record-video", dest="record", default=None
                    , help="Record session to video file.")

parser.add_argument("--start", dest="start", type=int, default=0
                    , help="Starting frame number for video file analysis.")

parser.add_argument("--stop", dest="stop", type=int, default=None
                    , help="Stop frame number for video file analysis.")

opts = parser.parse_args()

VERBOSE = 0 if opts.quiet else opts.verbose
smatch.VERBOSE = VERBOSE

video_writer = opts.record

if opts.video:
    try:                opts.video = int(opts.video)
    except ValueError:  pass
    frmbuf = VideoBuffer(opts.video,opts.start,opts.stop,historysize=LAST_DAY+1
                         , loop=opts.loop)

kbctrl = None

gmain_win = frmbuf.name
cv2.namedWindow(gmain_win, flags=cv2.WINDOW_NORMAL)
if opts.showmatches: cv2.namedWindow(gtemplate_win, flags=cv2.WINDOW_NORMAL)
smatch.MAIN_WIN = gmain_win
smatch.TEMPLATE_WIN = gtemplate_win


# ==========================================================
# Print intro output to user
# ==========================================================
if VERBOSE:
    print( "Options")
    print(( "-"*len("Options")))
    print(("- Subscribed to", (repr(opts.camtopic) if not opts.video else opts.video)))
    print(("- Hessian threshold set at", repr(opts.threshold)))
    print()

    print ("Additional controls")
    print(("-"*len("Additional controls")))
    print ("* Press 'q' at any time to quit")
    print ("* Press 'd' at any time to toggle keypoint drawing")
    if opts.video:
        print ("* Press 'm' at any time to toggle scale matching drawing")

# ==========================================================
# Additional setup before main loop
# ==========================================================
# initialize the feature description and matching methods
bfmatcher = cv2.BFMatcher()
surf_ui = cv2.SIFT_create()

# mask out a central portion of the image
try:
    lastFrame, t_last = frmbuf.grab()
    roi = np.zeros(lastFrame.shape,np.uint8)
    scrapY, scrapX = lastFrame.shape[0]//4, lastFrame.shape[1]//4
    roi[scrapY:-scrapY, scrapX:-scrapX] = True
except Exception as e:
    print(e)
    
idgen = uniqid_gen()
getuniqid = lambda : next(idgen)

# get keypoints and feature descriptors from query image and assign them an id
queryKP, qdesc = surf_ui.detectAndCompute(lastFrame,roi)
for kp in queryKP: kp.class_id = getuniqid()

# helper function
getMatchKPs = lambda x: (queryKP[x.queryIdx],trainKP[x.trainIdx])

# ==========================================================
# main loop
# ==========================================================
# errsum = 0
kpHist = OrderedDict()
while True:
    try:
        if frmbuf.looped:
            kpHist.clear()
            lastFrame, t_last = currFrame, t_curr
            queryKP, qdesc = surf_ui.detectAndCompute(lastFrame,roi)
            idgen = uniqid_gen()
            getuniqid = lambda : next(idgen)
            for kp in queryKP: kp.class_id = getuniqid()
            frmbuf.looped = False
    except AttributeError:
        pass
    currFrame, t_curr = frmbuf.grab()

    t1_loop = time.time() # loop timer
    if not currFrame.size: break
    dispim = cv2.cvtColor(currFrame,cv2.COLOR_GRAY2BGR)

    if VERBOSE > 2: print(("Frame time: %8.3f ms" % t_curr))

    '''
    First, assign _every_ query keypoint a unique ID
    Note: 1 and -1 are the openCV default class_ids
    '''
    for kp in queryKP:
        if kp.class_id in (1,-1): kp.class_id = getuniqid()

    # # attempt to adaptively threshold
    # err = len(trainKP)-TARGET_N_KP
    # surf_ui.hessianThreshold += 0.3*(err) + 0.05*(errsum+err)
    # if surf_ui.hessianThreshold < MIN_THRESH: surf_ui.hessianThreshold = MIN_THRESH
    # # elif surf_ui.hessianThreshold > MAX_THRESH: surf_ui.hessianThreshold = MAX_THRESH
    # errsum = len(trainKP)-TARGET_N_KP

    '''
    Now, define a one to one mapping to the training keypoints
    '''
    trainKP, tdesc = surf_ui.detectAndCompute(currFrame,roi)

    # Find the best K matches for each keypoint
    if tdesc is None or qdesc is None:  matches = []
    else:                               matches = bfmatcher.knnMatch(qdesc,tdesc,k=2)

    # Filter out poor matches by ratio test , maximum (descriptor) distance
    matchdist = []
    filteredmatches = []
    for m in matches:                           
        if (len(m)==2 and m[0].distance >= 0.8*m[1].distance) or m[0].distance >= 0.25:
            continue
        filteredmatches.append(m[0])
        qkp, tkp = getMatchKPs(m[0])
        tkp.class_id = qkp.class_id             # carry over the key point's ID
        matchdist.append(diffKP_L2(qkp,tkp))    # get the match pixel distance
    matches = filteredmatches

    if matchdist:       # Filter out matches with outlier spatial distances
        threshdist = np.mean(stats.trim1(matchdist,0.25)) + 2*np.std(matchdist)
        matches = [m for m,mdist in zip(matches,matchdist) if mdist < threshdist]

    if not opts.nodraw: # Draw rectangle around RoI
        cv2.rectangle(dispim,(scrapX,scrapY)
                      ,(currFrame.shape[1]-scrapX,currFrame.shape[0]-scrapY)
                      ,(192,192,192),thickness=2)

    if not opts.nodraw and matches: # Draw matched keypoints
        qkp, tkp = list(zip(*list(map(getMatchKPs,matches))))
        cv2.drawKeypoints(dispim, qkp, dispim, color=(0,255,0))
        cv2.drawKeypoints(dispim, tkp, dispim, color=(255,0,0))
        for q,t in zip(qkp,tkp): cv2.line(dispim, inttuple(*q.pt), inttuple(*t.pt), (0,255,0), 1)
        
    '''
    Find an estimate of the scale change for keypoints that are expanding
    Then update the history of expanding keypoints
    '''
    matches = [m for m in matches if trainKP[m.trainIdx].size > queryKP[m.queryIdx].size]
    matches, kpscales = smatch.estimateKeypointExpansion(frmbuf, matches, queryKP, trainKP, kpHist, 'L2')

    if opts.showmatches:
        lastkey = smatch.drawTemplateMatches(frmbuf, matches, queryKP, trainKP
                                             , kpHist, kpscales, dispim=dispim)
    else:
        lastkey = None

    keypoints = []
    for m,scale in zip(matches,kpscales):
        clsid = trainKP[m.trainIdx].class_id
        if clsid not in kpHist:
            kpHist[clsid] = KeyPointHistory()
            t_A = t_last
        else:                     
            t_A = kpHist[clsid].timehist[-1][-1]

        # update matched expanding keypoints with accurate scale, latest
        # keypoint and descriptor
        kpHist[clsid].update(trainKP[m.trainIdx],tdesc[m.trainIdx],t_A,t_curr,scale)
       
    # Update the keypoint history for previously expanding keypoint that were
    # not detected/matched in this frame
    detected = set(map(op.attrgetter('class_id'),trainKP))

    # get rid of old matches
    kpHist = OrderedDict([kv for kv in iter(kpHist.items()) if kv[1].downdate().age < LAST_DAY])

    # keep matches that were missed in this frame
    missed = [k for k in iter(kpHist.keys()) if (kpHist[k].age > 0) and (k not in detected)]
    missed = [(kpHist[k].keypoint,kpHist[clsid].descriptor.reshape(1,-1)) for k in missed]
    if missed:
        missed_kp, missed_desc = list(zip(*missed))
        trainKP = trainKP +  missed_kp
        tdesc = missed_desc[0] if tdesc is None else np.r_[tdesc, missed_desc[0]]

    '''
    Finally, perform some simple clustering of adjacent keypoints to
    obtain a more accurate estimate of TTC
    '''
    # cluster keypoints and sort my maximum inter-cluster distance
    # ttc_cluster = []
    # expandingKPs = filter(lambda x: (x.class_id in kpHist) and (kpHist[x.class_id].age == 0), trainKP)
    # cluster = ClusterKeypoints(expandingKPs, kpHist, currFrame)
    # for c in cluster:
    #     tstep = np.array( [op.sub(*reversed(kpHist[kp.class_id].timehist[-1])) for kp in c.KPs] )
    #     scale = np.array( [kpHist[kp.class_id].scalehist[-1] for kp in c.KPs] )
    #     ttc_cluster.append(np.median(tstep / scale))

    # if kbctrl and cluster:
    #     c = cluster[0]
    #     x_obs = c.pt[0]
    #     if (x_obs-currFrame.shape[1]//2) < 0: kbctrl.RollRight()
    #     if x_obs >= currFrame.shape[1]//2: kbctrl.RollLeft()

    # Print out drone status to the image
    if not opts.nodraw:
        if kbctrl:
            stat = "BATT=%.2f" % (kbctrl.navdata.batteryPercent)
            cv2.putText(dispim,stat,(10,currFrame.shape[0]-10)
                        ,cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,255))
        elif opts.video and not frmbuf.live:
            stat = "FRAME %4d/%4d" % (frmbuf.cap.get(cv2.CAP_PROP_POS_FRAMES),frmbuf.stop)
            cv2.putText(dispim,stat,(10,currFrame.shape[0]-10)
                        ,cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,255))

    # Draw expanding keypoints with tags
    if not opts.nodraw and opts.drawtags:
        expandingKPs = []
        for m in matches:
            qkp = queryKP[m.queryIdx]
            tkp = trainKP[m.trainIdx]
            scale = kpHist[tkp.class_id].scalehist[-1]
            tstep = -np.diff(kpHist[tkp.class_id].timehist[-1])
            # tstep = 1
            ttc = tstep / scale

            kpinfo = "(%d,%.2f,%.3f)" % (tkp.class_id,scale,ttc)
            cv2.putText(dispim,kpinfo,inttuple(tkp.pt[0]+tkp.size//2,tkp.pt[1]-tkp.size//2)
                        ,cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255,255,0))
            expandingKPs.append(kpHist[tkp.class_id].keypoint)

        cv2.drawKeypoints(dispim, expandingKPs, dispim, color=(0,0,255)
                          , flags=cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS)

        # # Draw clusters with tags
        # votes = [sum(kpHist[kp.class_id].detects for kp in c.KPs) for c in cluster]
        # for c, ttc in zip(cluster,ttc_cluster):
        #     clustinfo = "(%d,%.2f)" % (len(c.KPs),ttc)
        #     cv2.putText(dispim,clustinfo,(c.p1[0]-5,c.p1[1])
        #                 ,cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0,0,255))

        #     # Draw an arrow denoting the direction to avoid obstacle
        #     x_obs, y = c.pt
        #     if (x_obs-(currFrame.shape[1]//2)) < 0: offset = 50
        #     if x_obs >= (currFrame.shape[1]//2):    offset = -50
        #     cv2.arrowedLine(dispim, (currFrame.shape[1]//2,currFrame.shape[0] - 50)
        #                     , (currFrame.shape[1]//2+offset,currFrame.shape[0] - 50)
        #                     , (0,255,0), 3)

        #     # draw cluster ranking
        #     clr = (0,255-sum(kpHist[kp.class_id].detects for kp in c.KPs)*165./max(votes),255)
        #     cv2.rectangle(dispim,c.p0,c.p1,color=clr,thickness=2)

    '''
    Handle input keyboard events
    '''
    cv2.imshow(gmain_win, dispim)
    if opts.video:            # video file controls
       if lastkey in (ord('q'),ord('m')):
           k = lastkey
       elif lastkey is not None:
           k = cv2.waitKey(250)%256
           while k not in list(map(ord,('\r','s','q',' ','m','b','f'))): k = cv2.waitKey(250)%256
       elif not frmbuf.live:
           # limit the loop rate to 10 Hz the hacky way for display purposes
           t = (time.time()-t1_loop)
           k = cv2.waitKey(int(max((0.075-t)*1000,1)))%256
       else:
           k = cv2.waitKey(1)%256
       if k == ord('m'):
           opts.showmatches ^= True
           if opts.showmatches: cv2.namedWindow(gtemplate_win,cv2.WINDOW_NORMAL)
           else:                cv2.destroyWindow(gtemplate_win)
       while(k == ord('b')):
           frmbuf.seek(-2)
           cv2.imshow(gmain_win,frmbuf.grab()[0])
           k = cv2.waitKey(250)%256
       while(k == ord('f')):
           frmbuf.seek(1)
           cv2.imshow(gmain_win,frmbuf.grab()[0])
           k = cv2.waitKey(250)%256
    if k == ord('d'): opts.nodraw ^= True
    if k == ord('q'): break

    if opts.record: video_writer.write(dispim)

    # shift the buffer of loop data
    lastFrame   = currFrame
    queryKP     = trainKP
    qdesc       = tdesc
    t_last      = t_curr

# clean up
if opts.record: video_writer.release()
cv2.destroyAllWindows()
frmbuf.close()
