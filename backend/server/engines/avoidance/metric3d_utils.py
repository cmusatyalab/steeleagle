#!/usr/bin/env python3
"""
Metric3D Preprocessing and Postprocessing Utilities

This module provides the image preprocessing and postprocessing functions
needed for Metric3D depth estimation in the SteelEagle avoidance engine.
"""

import logging

import cv2
import numpy as np
import torch

logger = logging.getLogger(__name__)


class Metric3DPreprocessor:
    """
    Handles Metric3D-specific image preprocessing and postprocessing
    """

    def __init__(self, input_size=(616, 1064), device="cuda"):
        self.input_size = input_size  # (H, W)
        self.device = device

        # ImageNet normalization parameters
        self.mean = torch.tensor([123.675, 116.28, 103.53]).float()
        self.std = torch.tensor([58.395, 57.12, 57.375]).float()
        self.padding_value = [123.675, 116.28, 103.53]

    def preprocess_image(self, image):
        """
        Preprocess input image for Metric3D model inference

        Args:
            image (np.ndarray): Input image in RGB format (H, W, 3)

        Returns:
            tuple: (preprocessed_tensor, preprocessing_info)
        """
        if len(image.shape) != 3 or image.shape[2] != 3:
            raise ValueError(
                f"Expected RGB image with shape (H, W, 3), got {image.shape}"
            )

        original_shape = image.shape[:2]  # (H, W)

        # Calculate scaling to fit model input size while maintaining aspect ratio
        h, w = image.shape[:2]
        scale = min(self.input_size[0] / h, self.input_size[1] / w)
        new_h, new_w = int(h * scale), int(w * scale)

        # Resize image
        resized_image = cv2.resize(
            image, (new_w, new_h), interpolation=cv2.INTER_LINEAR
        )

        # Calculate padding
        pad_h = self.input_size[0] - new_h
        pad_w = self.input_size[1] - new_w
        pad_top = pad_h // 2
        pad_bottom = pad_h - pad_top
        pad_left = pad_w // 2
        pad_right = pad_w - pad_left

        # Apply padding
        padded_image = cv2.copyMakeBorder(
            resized_image,
            pad_top,
            pad_bottom,
            pad_left,
            pad_right,
            cv2.BORDER_CONSTANT,
            value=self.padding_value,
        )

        # Convert to tensor and normalize
        image_tensor = torch.from_numpy(padded_image.transpose(2, 0, 1)).float()
        mean = self.mean[:, None, None].to(self.device)
        std = self.std[:, None, None].to(self.device)
        image_tensor = (image_tensor.to(self.device) - mean) / std
        image_tensor = image_tensor.unsqueeze(0)  # Add batch dimension

        # Store preprocessing info for reversal
        preprocess_info = {
            "original_shape": original_shape,
            "scale": scale,
            "new_shape": (new_h, new_w),
            "padding": (pad_top, pad_bottom, pad_left, pad_right),
        }

        return image_tensor, preprocess_info

    def postprocess_depth(self, depth_tensor, preprocess_info):
        """
        Postprocess depth prediction to match original image resolution

        Args:
            depth_tensor (torch.Tensor): Raw depth prediction from model
            preprocess_info (dict): Information from preprocessing step

        Returns:
            np.ndarray: Depth map with original image resolution
        """
        # Remove batch dimension and move to CPU
        if depth_tensor.dim() == 4:
            depth = depth_tensor.squeeze(0).squeeze(0).cpu()
        elif depth_tensor.dim() == 3:
            depth = depth_tensor.squeeze(0).cpu()
        else:
            depth = depth_tensor.cpu()

        # Remove padding
        pad_top, pad_bottom, pad_left, pad_right = preprocess_info["padding"]
        depth = depth[
            pad_top : depth.shape[0] - pad_bottom, pad_left : depth.shape[1] - pad_right
        ]

        # Resize to original resolution
        original_h, original_w = preprocess_info["original_shape"]
        depth = (
            torch.nn.functional.interpolate(
                depth.unsqueeze(0).unsqueeze(0),
                size=(original_h, original_w),
                mode="bilinear",
                align_corners=False,
            )
            .squeeze()
            .numpy()
        )

        return depth

    def apply_canonical_transform(
        self, depth_map, intrinsic_focal_length=1000.0, target_focal_length=707.0
    ):
        """
        Apply canonical camera space transformation

        Args:
            depth_map (np.ndarray): Depth map in canonical space
            intrinsic_focal_length (float): Focal length of canonical camera (default: 1000.0)
            target_focal_length (float): Target camera focal length

        Returns:
            np.ndarray: Transformed depth map in metric space
        """
        # Transform from canonical space to metric space
        canonical_to_real_scale = target_focal_length / intrinsic_focal_length
        metric_depth = depth_map * canonical_to_real_scale

        # Clamp depth values to reasonable range
        metric_depth = np.clip(metric_depth, 0, 300)

        return metric_depth


class Metric3DInference:
    """
    Complete Metric3D inference pipeline for obstacle avoidance
    """

    def __init__(self, model, device="cuda"):
        self.model = model
        self.device = device
        self.preprocessor = Metric3DPreprocessor(device=device)

    def predict_depth(self, image, apply_canonical_transform=True):
        """
        Predict depth map from input image

        Args:
            image (np.ndarray): Input image in RGB format
            apply_canonical_transform (bool): Whether to apply canonical transformation

        Returns:
            np.ndarray: Depth map with same resolution as input image
        """
        # Preprocess image
        image_tensor, preprocess_info = self.preprocessor.preprocess_image(image)

        # Run inference
        with torch.no_grad():
            pred_depth, confidence, output_dict = self.model.inference(
                {"input": image_tensor}
            )

        # Postprocess to original resolution
        depth_map = self.preprocessor.postprocess_depth(pred_depth, preprocess_info)

        # Apply canonical transformation if requested
        if apply_canonical_transform:
            depth_map = self.preprocessor.apply_canonical_transform(depth_map)

        return depth_map
