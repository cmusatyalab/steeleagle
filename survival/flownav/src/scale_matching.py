import cv2
import numpy as np
from common import *

VERBOSE = 0
TEMPLATE_WIN = None
MAIN_WIN = None
SEARCH_RES = 20
MINSIZE = 1.2
scalerange = 1 + np.arange(SEARCH_RES+1)/float(2*SEARCH_RES)
KEYPOINT_SCALE = (MINSIZE*SEARCH_RES)/9

# need to check for overflow on multiply operations
def normalize(src,ksize=(8,8)):
    I = src.astype(np.float64)
    I_mean = cv2.blur(I,ksize,borderType=cv2.BORDER_REFLECT)
    I_var = cv2.blur(I**2,ksize,borderType=cv2.BORDER_REFLECT).astype(np.float64) - I_mean**2
    
    return (I - I_mean)/np.sqrt(I_var)

def drawTemplateMatches(frmbuf,matches,queryKPs,trainKPs,kphist,scales,dispim=None):
    tdispim = dispim.copy() if dispim is not None else frmbuf.grab(0)[0].copy()

    k = None
    trainImg = frmbuf.grab(0)[0]
    prevImg = frmbuf.grab(-1)[0]
    for m,scale in zip(matches,scales):
        qkp = queryKPs[m.queryIdx]
        tkp = trainKPs[m.trainIdx]

        # grab the frame where the keypoint was last detected
        if qkp.class_id in kphist:
            queryImg = frmbuf.grab(kphist[qkp.class_id].lastFrameIdx)[0]
        else:
            queryImg = prevImg

        # /* Extract the query and train image patch and normalize them. */ #
        x_qkp,y_qkp = qkp.pt
        r = qkp.size*KEYPOINT_SCALE // 2
        x0,y0 = trunc_coords(queryImg.shape,(x_qkp-r, y_qkp-r))
        x1,y1 = trunc_coords(queryImg.shape,(x_qkp+r, y_qkp+r))
        querypatch = queryImg[y0:y1, x0:x1]
        querypatch = (querypatch-np.mean(querypatch))/np.std(querypatch)

        x_tkp,y_tkp = tkp.pt
        r = qkp.size*KEYPOINT_SCALE*scalerange[-1] // 2        
        x0,y0 = trunc_coords(trainImg.shape,(x_tkp-r, y_tkp-r))
        x1,y1 = trunc_coords(trainImg.shape,(x_tkp+r, y_tkp+r))
        trainpatch = trainImg[y0:y1, x0:x1]
        trainpatch = (trainpatch-np.mean(trainpatch))/np.std(trainpatch)

        # recalculate the best matching scaled template
        r = qkp.size*KEYPOINT_SCALE*scale // 2
        x_tkp,y_tkp = x_tkp-x0,y_tkp-y0
        x0,y0 = trunc_coords(trainpatch.shape,(x_tkp-r, y_tkp-r))
        x1,y1 = trunc_coords(trainpatch.shape,(x_tkp+r, y_tkp+r))
        scaledtrain = trainpatch[y0:y1, x0:x1]
        scaledquery = cv2.resize(querypatch, scaledtrain.shape[::-1]
                                 , fx=scale, fy=scale
                                 , interpolation=cv2.INTER_LINEAR)

        # draw the query patch, the best matching scaled patch and the
        # training patch
        templimg = np.zeros((scaledquery.shape[0]
                             ,scaledquery.shape[1]+scaledtrain.shape[1]+querypatch.shape[1])
                            , dtype=trainImg.dtype) + 255

        # scale values for display
        querypatch = 255.*(querypatch - np.min(querypatch))/(np.max(querypatch) - np.min(querypatch))
        scaledtrain = 255.*(scaledtrain - np.min(scaledtrain))/(np.max(scaledtrain) - np.min(scaledtrain))
        scaledquery = 255.*(scaledquery - np.min(scaledquery))/(np.max(scaledquery) - np.min(scaledquery))

        drawInto(querypatch, templimg)
        drawInto(scaledquery,templimg,tl=(querypatch.shape[1],0))
        drawInto(scaledtrain,templimg,tl=(querypatch.shape[1]+scaledquery.shape[1],0))

        cv2.drawKeypoints(tdispim,[tkp], tdispim, color=(0,0,255)
                          ,flags=cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS)

        cv2.imshow(TEMPLATE_WIN, templimg.astype(np.uint8))
        cv2.imshow(MAIN_WIN, tdispim.astype(np.uint8))

    return k


def estimateKeypointExpansion(frmbuf, matches, queryKPs, trainKPs, kphist, method='L2sq'):
    scale_argmin = []
    expandingMatches = []

    res = np.zeros(len(scalerange))
    trainImg = frmbuf.grab(0)[0]
    prevImg = frmbuf.grab(-1)[0]
    for m in matches:
        qkp = queryKPs[m.queryIdx]
        tkp = trainKPs[m.trainIdx]

        # grab the frame where the keypoint was last detected
        if qkp.class_id in kphist:
            queryImg = frmbuf.grab(kphist[qkp.class_id].lastFrameIdx)[0]
        else:
            queryImg = prevImg

        # Extract the query and train image patch and normalize them
        x_qkp,y_qkp = qkp.pt
        r = qkp.size * KEYPOINT_SCALE // 2
        x0,y0 = trunc_coords(queryImg.shape,(x_qkp-r, y_qkp-r))
        x1,y1 = trunc_coords(queryImg.shape,(x_qkp+r, y_qkp+r))
        print(f"{x0},{y0},{x1},{y1}")
        querypatch = queryImg[y0:y1, x0:x1]
        if not querypatch.size: continue
        querypatch = (querypatch-np.mean(querypatch))/np.std(querypatch)

        x_tkp,y_tkp = tkp.pt
        r = qkp.size*KEYPOINT_SCALE*scalerange[-1] // 2
        x0,y0 = trunc_coords(trainImg.shape,(x_tkp-r, y_tkp-r))
        x1,y1 = trunc_coords(trainImg.shape,(x_tkp+r, y_tkp+r))
        trainpatch = trainImg[y0:y1, x0:x1]
        if not trainpatch.size: continue
        trainpatch = (trainpatch-np.mean(trainpatch))/np.std(trainpatch)

        # Scale up the query to perform template matching
        res[:] = np.nan
        x_tkp,y_tkp = x_tkp-x0,y_tkp-y0
        for i,scale in enumerate(scalerange):
            r = qkp.size*KEYPOINT_SCALE*scale // 2
            x0,y0 = trunc_coords(trainpatch.shape,(x_tkp-r, y_tkp-r))
            x1,y1 = trunc_coords(trainpatch.shape,(x_tkp+r, y_tkp+r))
            scaledtrain = trainpatch[y0:y1, x0:x1]
            if not scaledtrain.size: continue

            scaledquery = cv2.resize(querypatch,scaledtrain.shape[::-1]
                                     , fx=scale, fy=scale
                                     , interpolation=cv2.INTER_LINEAR)

            if method == 'corr':
                res[i] = np.sum(scaledquery*scaledtrain)
            elif method == 'L1':
                res[i] = np.sum(np.abs(scaledquery-scaledtrain))
            elif method == 'L2':
                res[i] = np.sqrt(np.sum((scaledquery-scaledtrain)**2))
            elif method == 'L2sq':
                res[i] = np.sum((scaledquery-scaledtrain)**2)
        if all(np.isnan(res)): continue
        res /= scalerange**2 # normalize over scale

        # determine if the min match is acceptable
        res_argmin = np.nanargmin(res)
        scalemin = scalerange[res_argmin]
        if (scalemin > MINSIZE) and (res[res_argmin] < 0.8*res[0]):
            scale_argmin.append(scalemin)
            expandingMatches.append(m)
            if VERBOSE > 1:
                print()
                print("class_id:",qkp.class_id)
                print("scale_range =", repr(scalerange)[6:-1])
                # print "residuals =", repr((res-np.nanmin(res))/(np.nanmax(res)-np.nanmin(res)))[6:-1]
                print("residuals =", repr(res)[6:-1])
                print("Number of previous detects:", kphist[qkp.class_id].detects if qkp.class_id in kphist else 0)
                # print "Number of previous scale estimates:", len(kphist[qkp.class_id].scalehist) if qkp.class_id in kphist else 1
                print("Frames since last detect:", abs(kphist[qkp.class_id].lastFrameIdx) if qkp.class_id in kphist else 1)
                # print "Frames since first detect:", kphist[qkp.class_id].age+1 if qkp.class_id in kphist else 1
                print("Template size =", querypatch.shape)
                print("Relative scaling of template:",scalemin)
                print("Nearest neighbor ratio:",res[res_argmin]/res[0])
        else:
            if VERBOSE > 2:
                print()
                print("could not match feature")
                print("class_id:",qkp.class_id)
                print("scale_range =", repr(scalerange)[6:-1])
                # print "residuals =", repr((res-np.nanmin(res))/(np.nanmax(res)-np.nanmin(res)))[6:-1]
                print("residuals =", repr(res)[6:-1])
                print("Number of previous detects:", kphist[qkp.class_id].detects if qkp.class_id in kphist else 0)
                # print "Number of previous scale estimates:", len(kphist[qkp.class_id].scalehist) if qkp.class_id in kphist else 1
                print("Frames since last detect:", abs(kphist[qkp.class_id].lastFrameIdx) if qkp.class_id in kphist else 1)
                # print "Frames since first detect:", kphist[qkp.class_id].age+1 if qkp.class_id in kphist else 1
                print("Template size =", querypatch.shape)
                print("Relative scaling of template:",scalemin)
                print("Nearest neighbor ratio:",res[res_argmin]/res[0])
        # scale_argmin.append(scalemin)
        # expandingMatches.append(m)

    return expandingMatches, scale_argmin
