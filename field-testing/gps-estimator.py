import numpy as np
from scipy.spatial.transform import Rotation as R

def find_intersection(target_dir, target_insct):
    plane_pt = np.array([0, 0, 0])
    plane_norm = np.array([0, 0, 1])

    if (plane_norm.dot(target_dir).all() == 0):
        return None

    t = (plane_norm.dot(plane_pt) - plane_norm.dot(target_insct)) / plane_norm.dot(target_dir)
    return target_insct + (t * target_dir)

if __name__ == "__main__":
    # Establish parameters.
    EARTH_RADIUS = 6378137.0
    drone_lat = 40.413493
    drone_lon = -79.949445 
    north_vec = np.array([0, 1, 0]) # Create a vector pointing due north.
    camera_pitch = 70 # Pitch of the gimbal.
    camera_yaw = -30 # Yaw of the drone.
    camera_elev = 5 # Elevation of the drone.
    target_x_pix = 380 # Location of target in X pixels.
    target_y_pix = 120 # Location of target in Y pixels.
    HFOV = 69 # Horizontal FOV.
    VFOV = 43 # Vertical FOV.
    pixel_center = (640/2, 480/2) # Center pixel location of the camera.

    # Perform rotations.
    r = R.from_euler('zyx', [camera_yaw, camera_pitch, 0], degrees=True) # Rotate the due north vector to camera center.
    camera_center = r.as_matrix().dot(north_vec)
    print("Camera centered at: {0}".format(camera_center))

    target_x_angle = -1 * ((target_x_pix - pixel_center[0]) / pixel_center[0]) * (HFOV / 2)
    target_y_angle = ((target_y_pix - pixel_center[1]) / pixel_center[1]) * (VFOV / 2)
    r = R.from_euler('zyx', [target_x_angle, target_y_angle, 0], degrees=True) # Rotate the camera center vector to target center.
    target_dir = r.as_matrix().dot(camera_center)
    print("Target centered at: {0}".format(target_dir))
    
    # Finding the intersection with the plane.
    insct = find_intersection(target_dir, np.array([0, 0, camera_elev]))
    print("Intersection with ground plane: {0}".format(insct))

    # Calculate distance and estimate GPS.
    dist = insct # Distance from the drone in meters.
    print("Distance from drone: {0}m".format(np.linalg.norm(dist)))
    
    dlat = (dist[1] / EARTH_RADIUS)
    dlon = (dist[0] / (EARTH_RADIUS * np.cos(np.pi * drone_lat / 180)))
    est_lat = drone_lat + dlat * 180 / np.pi;
    est_lon = drone_lon + dlon * 180 / np.pi;

    print("Estimated GPS location: ({0}, {1})".format(est_lat, est_lon))
