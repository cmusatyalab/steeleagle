#!/usr/bin/env python3
"""
Metric3D Model Loading Support for SteelEagle Avoidance Engine

This module provides simplified Metric3D model loading functionality
extracted from the original Metric3D hubconf.py for integration with
the SteelEagle obstacle avoidance system.
"""

import os
import torch
import logging

logger = logging.getLogger(__name__)

# Model configurations for torch.hub.load
MODEL_CONFIGS = {
    'metric3d_vit_small': {
        'repo': 'yvanyin/metric3d',
        'model': 'metric3d_vit_small'
    },
    'metric3d_vit_large': {
        'repo': 'yvanyin/metric3d', 
        'model': 'metric3d_vit_large'
    },
    'metric3d_vit_giant2': {
        'repo': 'yvanyin/metric3d',
        'model': 'metric3d_vit_giant2'
    },
    'metric3d_convnext_large': {
        'repo': 'yvanyin/metric3d',
        'model': 'metric3d_convnext_large'
    }
}

# Metric3D preprocessing constants
METRIC3D_INPUT_SIZE = (616, 1064)  # Standard input size for ViT models
IMAGENET_MEAN = [123.675, 116.28, 103.53]  # ImageNet normalization
IMAGENET_STD = [58.395, 57.12, 57.375]
PADDING_VALUE = [123.675, 116.28, 103.53]

class Metric3DModelLoader:
    """
    Simplified Metric3D model loader for obstacle avoidance integration
    """
    
    @staticmethod
    def load_model(model_name, device='cuda'):
        """
        Load a Metric3D model using torch.hub
        
        Args:
            model_name (str): Name of the model to load
            device (str): Device to load the model on
            
        Returns:
            torch.nn.Module: Loaded Metric3D model
        """
        if model_name not in MODEL_CONFIGS:
            raise ValueError(f"Unsupported model: {model_name}. "
                           f"Supported models: {list(MODEL_CONFIGS.keys())}")
        
        config = MODEL_CONFIGS[model_name]
        logger.info(f"Loading Metric3D model: {model_name}")
        
        # Load model using torch.hub
        model = torch.hub.load(
            config['repo'], 
            config['model'], 
            pretrain=True,
            trust_repo=True  # Allow loading from external repos
        )
        
        # Move to device and set to evaluation mode
        model = model.to(device)
        model.eval()
        
        logger.info(f"Successfully loaded {model_name} on {device}")
        return model
    
    @staticmethod  
    def get_preprocessing_params():
        """
        Get preprocessing parameters for Metric3D models
        
        Returns:
            dict: Preprocessing parameters
        """
        return {
            'input_size': METRIC3D_INPUT_SIZE,
            'mean': IMAGENET_MEAN,
            'std': IMAGENET_STD,
            'padding_value': PADDING_VALUE
        }


# Compatibility function to match the torch.hub interface
def load_metric3d_model(model_name, pretrain=True, device='cuda'):
    """
    Load Metric3D model with torch.hub compatible interface
    
    Args:
        model_name (str): Model name
        pretrain (bool): Whether to load pretrained weights (always True for hub models)
        device (str): Device to load on
        
    Returns:
        torch.nn.Module: Loaded model
    """
    return Metric3DModelLoader.load_model(model_name, device)