import sys
import cv2
import numpy as np

VERBOSE = 0


class VideoBuffer(object):
    def __init__(self,vidfile,start=None,stop=None,loop=False,historysize=1):
        self.cap = cv2.VideoCapture(vidfile)
        self.name = str(vidfile)
        self.live = not isinstance(vidfile,str)
        self.start = start
        self.stop = stop
        self.loop = loop
        self._size = historysize
        self._frameNum = 0
        self._buffer = []

        if not self.live:
            if self.start is None:
                self.start = self.cap.get(cv2.CAP_PROP_POS_FRAMES)
            if self.stop is None:
                self.stop = self.cap.get(cv2.CAP_PROP_FRAME_COUNT)
        self._reset()
        self.looped = False

    @property
    def frameNum(self): return self._frameNum

    def _reset(self):
        if not self.live:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.start)
            self._frameNum = self.start
            self.looped = self.cap.get(cv2.CAP_PROP_POS_FRAMES) == self.stop
        self._buffer = [np.array([])]*self._size
        self.shiftBuffer(self._size)

    def shiftBuffer(self,nshifts=1):
        for i in range(nshifts):
            if not self.live and self.cap.get(cv2.CAP_PROP_POS_FRAMES) == self.stop:
                if not self.loop: return False
                self._reset()

            valid, img = self.cap.read()
            if not valid: return False

            img = cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
            time = -1 if self.live else self.cap.get(cv2.CAP_PROP_POS_MSEC)

            self._buffer[:-1] = self._buffer[1:]
            self._buffer[-1] = (img,time)
        return True

    def grab(self,frameIdx=1):
        if frameIdx > 0:
            if not self.shiftBuffer(): return np.array([]), -1
            frameIdx = -1
            self._frameNum += 1
        else:
            frameIdx -= 1
            
        return self._buffer[frameIdx]

    def seek(self,nframes):
        if self.live: return

        framenum = self.cap.get(cv2.CAP_PROP_POS_FRAMES)+nframes-self._size
        self.cap.set(cv2.CAP_PROP_POS_FRAMES
                     ,self.stop-self._size if framenum > (self.stop-self._size) else max(self._size,framenum))
        stat = self.shiftBuffer(self._size)

    def close(self):
        self.cap.release()
        del self._buffer


