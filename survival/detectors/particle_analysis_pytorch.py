import torch
from torchvision import transforms
import time
import numpy as np
from detectors.detector_base import DetectorBase
import cv2
import socket

# --- MiDaS ---

class ParticleAnalysis(DetectorBase):

    minArea = 1000
    # model_type = "DPT_Large"     # MiDaS v3 - Large     (highest accuracy, slowest inference speed)
    model_type = "DPT_Hybrid"   # MiDaS v3 - Hybrid    (medium accuracy, medium inference speed)
    # model_type = "MiDaS_small"  # MiDaS v2.1 - Small   (lowest accuracy, highest inference speed)

    midas = torch.hub.load("intel-isl/MiDaS", model_type)

    # Move model to GPU if available
    midas.to(torch.device("cuda"))
    midas.eval()


    # Load transforms to resize and normalize the image
    midas_transforms = torch.hub.load("intel-isl/MiDaS", "transforms")

    if model_type == "DPT_Large" or model_type == "DPT_Hybrid":
        transform = midas_transforms.dpt_transform
    else:
        transform = midas_transforms.small_transform


    def detect(self, frame):

        start = time.time()
        img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Apply input transforms
        input_batch = self.transform(img).to(torch.device("cuda"))

        # Prediction and resize to original resolution
        with torch.no_grad():
            prediction = self.midas(input_batch)

            prediction = torch.nn.functional.interpolate(
                prediction.unsqueeze(1),
                size=img.shape[:2],
                mode="bicubic",
                align_corners=False,
            ).squeeze()

        depth_map = prediction.cpu().numpy()

        depth_map = cv2.normalize(depth_map, None, 0, 1, norm_type=cv2.NORM_MINMAX, dtype=cv2.CV_64F)

        end = time.time()
        fps = 1 / (end - start)

        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

        depth_map = (depth_map*255).astype(np.uint8)
        depth_map = cv2.applyColorMap(depth_map , cv2.COLORMAP_MAGMA)

        cv2.imshow('Depth', depth_map)
        cv2.waitKey(1)

        return frame
