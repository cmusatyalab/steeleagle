import time
import sys
import os
import logging
import json
import argparse

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class Coordinate():
    def __init__(self, x, y, alt):
        self.lat = y
        self.long = x
        self.alt = alt

class PathStore():
    def __init__(self, filename, home):
        self.waypoint_file = filename
        self.home = home
        self.total_waypoints = 0
        self.current_waypoint = 0
        self.waypoints = {}
        self.name = ""

    def set_drone_name(self, name):
        self.name = name
    
    def load_waypoint(self, waypoint):
        self.waypoints[self.total_waypoints] = waypoint
        self.total_waypoints += 1

    def remove_waypoint_by_id(self, id):
        if id not in self.waypoints:
            logger.info(f"Attempted to remove waypoint not in store, id: {id}")
        else:
            del self.waypoints[id]
            logger.info(f"Removed waypoint id: {id}")
    
    def get_next_waypoint(self):
        if self.current_waypoint >= self.total_waypoints:
            logger.info(f"No waypoints remaining. Last waypoint id: {self.current_waypoint}")
            return None
        next_waypoint = self.waypoints
        self.current_waypoint += 1
        return next_waypoint
    
    def extract_waypoints(self):
        with open(self.waypoint_file, 'r') as file:
            data = json.load(file)
        print(data)

class PathValidator():
    def __init__(self, waypoint_file, mission_file, drone_count, lat, long, alt):
        self.path_list = []
        self.waypoint_file = waypoint_file
        self.mission_file = mission_file
        self.drone_count = drone_count
        self.home = Coordinate(long, lat, alt)
    
    def parse_paths(self):
        drone_path = PathStore(self.waypoint_file, self.home)
        drone_path.extract_waypoints()

    def run_mission(self, mission_store):
        pass

    def replay_mission(self, mission_store):
        pass

    def set_simulation_speed(self, new_speed):
        pass

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'waypoint_file', help='path to waypoint file being validated', type=str, default=""
    )
    parser.add_argument(
        '-m', '--mission-file', help='path to mission file being validated', type=str, default=""
    )
    parser.add_argument(
        '-d', '--drones', help='number of drones to simulate', type=int, default=1
    )
    parser.add_argument(
        '--lat', help='origin point latitude', type=float, default=-1.0
    )
    parser.add_argument(
        '--long', help='origin point longitude', type=float, default=-1.0
    )
    parser.add_argument(
        '-a', '--alt', help='origin point altitude', type=float, default=0.0
    )
    args = parser.parse_args()

    validator = PathValidator(args.waypoint_file, args.mission_file, args.drones, args.lat, args.long, args.alt)
    validator.parse_paths()
    return 0


if __name__ == "__main__":
    sys.exit(main())