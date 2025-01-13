import collections
try:
    import collections.abc as collections_abc
except ImportError:
    import collections as collections_abc 
collections.MutableMapping = collections.abc.MutableMapping

from dronekit import connect

# Replace with the IP address of your drone
drone_ip = "0.0.0.0"
drone_port = '14550'
connection_string = f'tcp:{drone_ip}:{drone_port}'

# Connect to the vehicle
print(f"Connecting to drone at {connection_string}...")
vehicle = connect(connection_string, wait_ready=True)

# Print some basic drone information
print(f"Connected to vehicle: {vehicle.version}")
print(f"GPS: {vehicle.gps_0}")
print(f"Battery: {vehicle.battery}")
print(f"Last Heartbeat: {vehicle.last_heartbeat}")

# Close the connection when done
vehicle.close()

