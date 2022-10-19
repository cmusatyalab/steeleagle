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
    drone_lat = 40.413173
    drone_lon = -79.949509
    north_vec = np.array([0, 1, 0]) # Create a vector pointing due north.
    camera_pitch = -25 # Pitch of the gimbal.
    camera_yaw = 90 # Yaw of the drone.
    camera_elev = 5 # Elevation of the drone.
    target_x_pix = 380 # Location of target in X pixels.
    target_y_pix = 120 # Location of target in Y pixels.
    HFOV = 69 # Horizontal FOV.
    VFOV = 43 # Vertical FOV.
    pixel_center = (640/2, 480/2) # Center pixel location of the camera.

    print("Pitch: {0}, Yaw: {1}, Elev: {2}".format(camera_pitch, camera_yaw, camera_elev))

    # Perform rotations.
    r = R.from_euler('ZYX', [camera_yaw, 0, camera_pitch], degrees=True) # Rotate the due north vector to camera center.
    camera_center = r.as_matrix().dot(north_vec)

    print("Camera centered at: ({0}, {1}, {2})".format(camera_center[0], camera_center[1], camera_center[2]))

    target_yaw_angle = -1 * ((target_x_pix - pixel_center[0]) / pixel_center[0]) * (HFOV / 2)
    target_pitch_angle = ((target_y_pix - pixel_center[1]) / pixel_center[1]) * (VFOV / 2)
    r = R.from_euler('ZYX', [camera_yaw + target_yaw_angle, 0, camera_pitch + target_pitch_angle], degrees=True) # Rotate the camera center vector to target center.
    target_dir = r.as_matrix().dot(north_vec)
    print("Target yaw: {0}, Target pitch: {1}".format(target_yaw_angle, target_pitch_angle))
    print("Target centered at: ({0}, {1}, {2})".format(target_dir[0], target_dir[1], target_dir[2]))
   
    n = np.array([0, 0, 1])       
    n_norm = np.sqrt(sum(n**2))    
    proj_of_u_on_n = (np.dot(target_dir, n)/n_norm**2)*n
    v = target_dir - proj_of_u_on_n
    print("Projection of Vector u on Plane P is: ", np.linalg.norm(v))

    # Finding the intersection with the plane.
    insct = find_intersection(target_dir, np.array([0, 0, camera_elev]))
    print("Intersection with ground plane: ({0}, {1}, {2})".format(insct[0], insct[1], insct[2]))

    # Calculate distance and estimate GPS.
    dist = np.linalg.norm(insct) # Distance from the drone in meters.
    print("Distance from drone: {0}m".format(dist))
    head = np.arccos(north_vec.dot(insct) / (np.linalg.norm(north_vec) * np.linalg.norm(insct)))
    print("Heading angle: {0} deg".format(head * (180 / np.pi)))

    est_lat = drone_lat + (180 / np.pi) * (insct[1] / EARTH_RADIUS)
    est_lon = drone_lon + (180 / np.pi) * (insct[0] / EARTH_RADIUS) / np.cos(drone_lat)
    print("Estimated GPS location: ({0}, {1})".format(est_lat, est_lon))
