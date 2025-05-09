import numpy as np
import os

def read_transform_matrix(filename="slam_transform_matrix.txt"):
    """
    Read a 4x4 transformation matrix from a file in the current directory.
    
    Args:
        filename (str): Name of the file containing the transformation matrix.
        
    Returns:
        numpy.ndarray: The 4x4 transformation matrix.
    """
    filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    try:
        with open(filepath, 'r') as f:
            lines = f.readlines()
            matrix = np.zeros((4, 4))
            for i, line in enumerate(lines):
                matrix[i] = np.array([float(val) for val in line.strip().split()])
        return matrix
    except Exception as e:
        print(f"Error reading transformation matrix: {e}")
        return None

def transform_point(matrix, point):
    """
    Transform a 3D point using the transformation matrix.
    
    Args:
        matrix (numpy.ndarray): 4x4 transformation matrix.
        point (tuple or list): (x, y, z) coordinates.
        
    Returns:
        numpy.ndarray: Transformed (x, y, z) coordinates.
    """
    if matrix is None:
        return None
    
    # Convert point to homogeneous coordinates
    homogeneous_point = np.array([point[0], point[1], point[2], 1.0])
    
    # Apply transformation
    transformed = matrix @ homogeneous_point
    
    # Convert back to 3D coordinates (divide by w if necessary)
    if transformed[3] != 0:
        transformed = transformed / transformed[3]
    
    return transformed[:3]

# Example usage
if __name__ == "__main__":
    # Read the transformation matrix
    transform = read_transform_matrix()
    
    if transform is not None:
        print("Transformation Matrix:")
        print(transform)
        
        # Example point
        test_point = (1.0, 2.0, 3.0)
        transformed_point = transform_point(transform, test_point)
        
        print(f"\nOriginal point: {test_point}")
        print(f"Transformed point: {transformed_point}") 