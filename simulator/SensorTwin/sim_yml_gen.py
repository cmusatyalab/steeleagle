# Drone Count
# Origin Location (GPS)
# Object Locations? (Or do this as a separate file?)
# Per Drone
# - Drone_ID
# - Drone_Type
# - Drone Max Speed
# - Drone Origin (GPS)
# - Gimbal Orientation

import sys
import yaml
import argparse

class SimulatedDrone:
    def __init__(self, id, dtype, speed, dorigin, gorientation):
        self.drone_ID = id
        self.drone_type = dtype
        self.max_speed = speed
        self.origin = dorigin
        self.gimbal_orientation = gorientation
    
    def convert_to_yaml(self):
        data = {
            'drone_ID' : self.drone_ID,
            'drone_type' : self.drone_type,
            'max_speed' : self.max_speed,
            'origin' : self.origin,
            'gimbal_orientation' : self.gimbal_orientation
        }
        return data

def create_predefined_drone(drone_type: str, drone_id: int, starting_loc: tuple[float, float], g_orient: float) -> SimulatedDrone:
    pass

def manual_drone_input(drone_count: int) -> list[SimulatedDrone]:
    drones = []
    counter = 0
    while counter < drone_count:
        d_id = counter + 1
        d_type = input("Enter drone type: ")
        d_speed = input("Enter max speed of drone: ")
        lat = input(f"Enter starting latitude for drone {counter + 1}: ")
        long = input(f"Enter starting longitude for drone {counter + 1}: ")
        g_orientation = input("Enter gimble orientation: ")
        new_drone = SimulatedDrone(d_id, d_type, d_speed, (lat, long), g_orientation)
        drones.append(new_drone.convert_to_yaml())
        drone_count += 1
    return drones

def check_type_args(type_list_len: int, drone_count: int) -> bool:
    if drone_count < 1 or type_list_len < 1:
        print("Invalid drone count or type list length")
        return False
    if type_list_len > 1 and type_list_len != drone_count:
        print("Not enough drone types specified. List each drone type individual or a single type for the group")
        return False
    else:
        return True
    
def check_drone_types(type_list: list[str]):
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('output_file', help='Output filename', type=str)
    parser.add_argument('-c', '--count', help='Number of drones to simulate', type=int, default=1)
    parser.add_argument('-o', '--origin', help='Origin loc for map in GPS coordinates', type=tuple[float, float], default=(0.0, 0.0))
    parser.add_argument('-dt', '--drone_type', nargs='*', help='Optional model specification for each simulated drone', type=str, default=['parrot_perfect'])
    parser.add_argument('-s', '--spread', help='Distance in meters to separate each drone starting location', type=float, default=10.0)
    parser.add_argument('-g', '--gimble', help='Orientation of the gimbal in degrees within range [0.0, 90.0]', type=float, default=45.0)
    parser.add_argument('-m', '--manual', help='Manually define drone characteristics by std input', action='store_true', default=False)
    args = parser.parse_args()

    filename = args.output_file
    drone_count = args.count
    global_origin = args.origin
    type_list = args.drone_type
    starting_spread = args.spread
    gimbal_orientation = args.gimble
    manual_entry_flag = args.manual
    type_list_len = len(type_list)

    if not check_type_args(type_list_len, drone_count):
        sys.exit()
    
    if not manual_entry_flag and not check_drone_types(type_list):
        sys.exit()
    
    drones = []
    counter = 0
    if manual_entry_flag:
        drones = manual_drone_input(drone_count)
    else:
        while counter < drone_count:
            drones.append(create_predefined_drone(type_list[counter % type_list_len], counter + 1,
                (global_origin[0], global_origin[1] + (starting_spread * counter)), gimbal_orientation))
            counter += 1

    data = {
        'drone_count' : drone_count,
        'origin' : {'lat' : global_origin[0], 'long' : global_origin[1]},
        'drones' : drones
    }

    output_string = yaml.dump(data, default_flow_style=False)
    print(output_string)

    with open(filename, 'w') as file:
        yaml.dump(data, file, default_flow_style=False)

