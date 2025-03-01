# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

from operator import attrgetter

import cv2
import numpy as np


class KeyPointHistory:
    def __init__(self):
        self.age = -1
        self.lastFrameIdx = 0
        self.detects = 0
        self.scalehist = []
        self.timehist = []
        self.keypoint = None
        self.descriptor = None
        self.consecutive = 0

    def update(self, kp, desc, t0, t1, scale):
        if self.timehist and t0 == self.timehist[-1][-1]:
            self.consecutive += 1
        else:
            self.consecutive = 1

        self.age = -1
        self.lastFrameIdx = 0
        self.detects += 1
        self.scalehist.append(scale)
        self.timehist.append((t0, t1))
        self.descriptor = desc.copy()
        self.keypoint = copyKP(kp)

    def downdate(self):
        self.age += 1
        self.lastFrameIdx -= 1
        return self

    def __repr__(self):
        return repr(
            dict(
                (attr, getattr(self, attr))
                for attr in dir(self)
                if not attr.startswith("_") and not callable(getattr(self, attr))
            )
        )

    def __str__(self):
        return str(
            dict(
                (attr, getattr(self, attr))
                for attr in dir(self)
                if not attr.startswith("_") and not callable(getattr(self, attr))
            )
        )


class Cluster:
    def __init__(self, keypoints, img):
        self.mask = np.zeros_like(img)
        for kp in keypoints:
            cv2.circle(self.mask, inttuple(*kp.pt), int(kp.size // 2), 1, thickness=-1)
        self.area = np.sum(self.mask)
        self.pt = findCoM(self.mask)
        self.p0, self.p1 = BlobBoundingBox(self.mask)
        self.KPs = [copyKP(kp) for kp in keypoints]
        self.dist = [
            diffKP_L2(self.KPs[i], self.KPs[j])
            for i in range(len(self.KPs) - 1)
            for j in range(i + 1, len(self.KPs))
        ]

    def __repr__(self):
        return str(map(repr, (self.pt, self.area, len(self.KPs))))


def BlobBoundingBox(blob):
    diff = blob.any(axis=0)
    ones = np.flatnonzero(diff)
    xmin, xmax = ones[0], ones[-1]

    diff = blob.any(axis=1)
    ones = np.flatnonzero(diff)
    ymin, ymax = ones[0], ones[-1]

    return (xmin, ymin), (xmax, ymax)


def findCoM(mask):
    colnums = np.arange(np.shape(mask)[1]).reshape(1, -1)
    rownums = np.arange(np.shape(mask)[0]).reshape(-1, 1)

    x = np.sum(mask * colnums) // np.sum(mask)
    y = np.sum(mask * rownums) // np.sum(mask)

    return x, y


def trunc_coords(shape, xy):
    return [
        round(x) if x >= 0 and x <= dimsz else (0 if x < 0 else dimsz)
        for dimsz, x in zip(shape[::-1], xy)
    ]


def bboverlap(cl1, cl2):
    return (cl1.p0[0] <= cl2.p1[0] and cl1.p1[0] >= cl2.p0[0]) and (
        cl1.p0[1] <= cl2.p1[1] and cl1.p1[1] >= cl2.p0[1]
    )


def overlap(kp1, kp2, eps=0):
    return (kp1.size // 2 + kp2.size // 2 + eps) > diffKP_L2(kp1, kp2)


def diffKP_L2(kp0, kp1):
    return np.sqrt((kp0.pt[0] - kp1.pt[0]) ** 2 + (kp0.pt[1] - kp1.pt[1]) ** 2)


def diffKP(kp0, kp1):
    return (kp0.pt[0] - kp1.pt[0], kp0.pt[1] - kp1.pt[1])


def difftuple_L2(p0, p1):
    return np.sqrt((p0[0] - p1[0]) ** 2 + (p0[1] - p1[1]) ** 2)


def difftuple(p0, p1):
    return (p1[0] - p0[0], p1[1] - p0[1])


def inttuple(*x):
    return tuple(map(int, x))


def roundtuple(*x):
    return tuple(map(int, map(round, x)))


def avgKP(keypoints):
    return map(lambda x: sum(x) / len(keypoints), zip(*map(attrgetter("pt"), keypoints)))


def toKeyPoint_cv(kp):
    return cv2.KeyPoint(
        kp.pt[0],
        kp.pt[1],
        kp.size,
        _angle=kp.angle,
        _response=kp.response,
        _octave=kp.octave,
        _class_id=kp.class_id,
    )


def reprObj(obj):
    return "\n".join(
        [
            f"{attr} = {getattr(obj, attr)}"
            for attr in dir(obj)
            if not attr.startswith("_") and not callable(getattr(obj, attr))
        ]
    )


def cvtIdx(pt, shape):
    return (
        int(pt[1] * shape[1] + pt[0])
        if hasattr(pt, "__len__")
        else map(int, (pt % shape[1], pt // shape[1]))
    )


def drawInto(src, dst, tl=(0, 0)):
    dst[tl[1] : tl[1] + src.shape[0], tl[0] : tl[0] + src.shape[1]] = src


def copyKP(src, dst=None):
    if dst is None:
        dst = cv2.KeyPoint()
    for attr in dir(src):
        if not attr.startswith("_") and not callable(getattr(src, attr)):
            setattr(dst, attr, getattr(src, attr))
    return dst
