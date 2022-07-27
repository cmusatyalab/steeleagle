import cv2
import io
import socket
import struct
import time
import pickle
import numpy as np
import imutils


client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client_socket.connect(('128.2.212.51', 8485))

cam = cv2.VideoCapture(0)
img_counter = 0

#encode to jpeg format
#encode param image quality 0 to 100. default:95
#if you want to shrink data size, choose low image quality.
encode_param=[int(cv2.IMWRITE_JPEG_QUALITY),80]

while True:
    ret, frame = cam.read()
    frame = imutils.resize(frame, width=320)
    frame = cv2.flip(frame, 180)
    result, image = cv2.imencode('.jpg', frame, encode_param)
    data = pickle.dumps(image, 0)
    size = len(data)

    if img_counter%10==0:
        client_socket.sendall(struct.pack(">L", size) + data)
        # cv2.imshow('client',frame)
        
    img_counter += 1

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
    

cam.release()