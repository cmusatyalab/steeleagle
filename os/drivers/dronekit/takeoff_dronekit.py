import collections
if not hasattr(collections, 'MutableMapping'):
    import collections.abc
    collections.MutableMapping = collections.abc.MutableMapping

from dronekit import connect, VehicleMode
import time


def main():
    # Connect to the SITL vehicle
    print("Connecting to SITL...")
    vehicle = connect('udp:0.0.0.0:14550', wait_ready=True)

    # Display basic vehicle information
    print(f"Connected to vehicle on: {vehicle.version}")
    print(f"Autopilot Firmware: {vehicle.version}")
    print(f"Global Location: {vehicle.location.global_frame}")
    print(f"Battery: {vehicle.battery}")
    print(f"Last Heartbeat: {vehicle.last_heartbeat}")

    # Wait for the vehicle to be armable
    print("Waiting for vehicle to initialize...")
    while not vehicle.is_armable:
        print("Waiting for vehicle to become armable...")
        time.sleep(1)

    # Set mode to GUIDED
    print("Setting vehicle to GUIDED mode...")
    vehicle.mode = VehicleMode("GUIDED")
    while vehicle.mode != "GUIDED":
        print("Waiting for GUIDED mode...")
        time.sleep(1)
    print("GUIDED mode set.")

    # Arm the drone
    print("Arming the drone...")
    vehicle.armed = True
    while not vehicle.armed:
        print("Waiting for arming...")
        time.sleep(1)
    print("Drone armed!")

    # Take off
    target_altitude = 10  # Altitude in meters
    print(f"Taking off to {target_altitude} meters...")
    vehicle.simple_takeoff(target_altitude)

    # Wait until the vehicle reaches the target altitude
    while True:
        print(f"Current altitude: {vehicle.location.global_relative_frame.alt:.2f} meters")
        if vehicle.location.global_relative_frame.alt >= target_altitude * 0.95:  # Within 95% of target altitude
            print("Target altitude reached!")
            break
        time.sleep(1)

    # Hover for a few seconds
    print("Hovering for 5 seconds...")
    time.sleep(5)

    # Land the vehicle
    print("Landing...")
    vehicle.mode = VehicleMode("LAND")
    while vehicle.mode != "LAND":
        print("Waiting for LAND mode...")
        time.sleep(1)
    print("Landing initiated.")

    # Wait for the vehicle to land
    while vehicle.armed:
        print("Waiting for landing to complete...")
        time.sleep(1)
    print("Landed and disarmed.")

    # Close the connection
    print("Closing vehicle connection...")
    vehicle.close()
    print("Connection closed.")


if __name__ == "__main__":
    main()

