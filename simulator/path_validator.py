import argparse
import json
import logging
import sys
import time

import folium
import streamlit as st
from streamlit_folium import st_folium

logging.basicConfig(stream=sys.stdout)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

DEFAULT_LAT = 40.41368353053923
DEFAULT_LONG = -79.9489233699767


class Coordinate:
    def __init__(self, x, y, alt):
        self.long = x
        self.lat = y
        self.alt = alt

    def to_tuple(self):
        return (self.lat, self.long)

    def __sub__(self, other):
        return Coordinate(
            self.long - other.long, self.lat - other.lat, self.alt - other.alt
        )

    def __repr__(self):
        return f"({self.long}, {self.lat}, {self.alt})"


class PathStore:
    def __init__(self, filename, table_prefix, home):
        self.waypoint_file = filename
        self.table_prefix = table_prefix
        self.home = home
        self.total_legs = 0
        self.total_waypoints = 1
        self.current_waypoint = 0
        self.waypoints = [home]
        self.name = ""

    def set_drone_name(self, name):
        self.name = name

    def set_current_waypoint(self, id):
        if id >= self.total_waypoints:
            logger.error("Set index out of path's waypoint bounds")
            return
        self.current_waypoint = id

    def load_waypoints_from_leg(self, flight_leg):
        for waypoint in flight_leg:
            self.waypoints.append(waypoint)
        self.total_waypoints += len(flight_leg)

    def remove_waypoint_by_index(self, id):
        if id not in self.waypoints:
            logger.info(f"Attempted to remove waypoint not in store, id: {id}")
        else:
            del self.waypoints[id]
            logger.info(f"Removed waypoint id: {id}")

    def get_current_waypoint(self):
        if self.current_waypoint >= self.total_waypoints:
            logger.info(
                f"No waypoints remaining. Last waypoint id: {self.current_waypoint - 1}"
            )
            return None
        return self.waypoints[self.current_waypoint]

    def get_next_waypoint(self):
        if self.current_waypoint >= self.total_waypoints - 1:
            logger.info(
                f"No waypoints remaining. Last waypoint id: {self.current_waypoint - 1}"
            )
            return None
        self.current_waypoint += 1
        return self.waypoints[self.current_waypoint]

    def load_waypoints(self):
        # NOTE: Key names are 1-indexed in the compiler output waypoint file
        with open(self.waypoint_file) as file:
            data = json.load(file)
        self.total_legs = len(data[self.table_prefix])
        for i in range(self.total_legs):
            flight_leg = value_to_coord_list(
                data[self.table_prefix][f"{self.table_prefix}_{i + 1}"]
            )
            self.load_waypoints_from_leg(flight_leg)
        # Assumes RTH after path completion
        self.waypoints.append(self.home)
        self.total_waypoints += 1

    def is_path_complete(self):
        return self.current_waypoint + 1 == self.total_waypoints

    def move_next_waypoint(self):
        logger.info(
            f"Moving from id: {self.current_waypoint} to id: {self.current_waypoint + 1}"
        )
        curr_waypoint = self.get_current_waypoint()
        next_waypoint = self.get_next_waypoint()
        logger.info(f"{curr_waypoint} ---> {next_waypoint}")


class PathValidator:
    def __init__(
        self, waypoint_file, mission_file, table_prefix, drone_count, lat, long, alt
    ):
        self.path_list = []
        self.waypoint_file = waypoint_file
        self.mission_file = mission_file
        self.table_prefix = table_prefix
        self.drone_count = drone_count
        self.home = Coordinate(long, lat, alt)
        self.tick_rate = 1

    def parse_paths(self):
        drone_path = PathStore(self.waypoint_file, self.table_prefix, self.home)
        drone_path.load_waypoints()
        self.path_list.append(drone_path)

    def run_path(self, path: PathStore):
        while not path.is_path_complete():
            path.move_next_waypoint()

    def replay_path(self, path: PathStore, start_point=0):
        if start_point >= path.total_waypoints:
            logger.error("Replay index out of path's waypoint bounds")
            return
        path.set_current_waypoint(start_point)
        self.run_path(path)

    def set_simulation_speed(self, new_speed: float):
        if new_speed <= 0:
            logger.error(
                "Attempted to set simulation speed to invalid value."
                "Tick rate must be positive"
            )
            return
        self.tick_rate = new_speed


# UTILITY FUNCTIONS #


def value_to_coord_list(dict_value: list[Coordinate], alt: float = 0.0):
    coord_list = []
    for points in dict_value:
        # Assumes format is [Long, Lat, Alt]
        if len(points) == 3:
            coord_list.append(Coordinate(points[0], points[1], points[2]))
        else:
            coord_list.append(Coordinate(points[0], points[1], alt))
    return coord_list


def calc_vector_to(start_pos: Coordinate, target_pos: Coordinate):
    return target_pos - start_pos


def render_test(path: PathStore):
    st.title("Path Validator")
    test_map = folium.Map(
        location=[40.4125, -79.9475], zoom_start=17, control_scale=True
    )
    path.set_current_waypoint(0)
    line_seg = []
    while not path.is_path_complete():
        line_seg.append(
            draw_path(path.get_current_waypoint(), path.get_next_waypoint())
        )
        for lines in line_seg:
            lines.add_to(test_map)
        st_data = st_folium(test_map, width=800)
        time.sleep(0.25)


def draw_path(curr_point: Coordinate, next_point: Coordinate):
    coords = [curr_point.to_tuple(), next_point.to_tuple()]
    return folium.PolyLine(locations=coords, weight=3, color="blue")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "waypoint_file",
        help="path to waypoint file being validated",
        type=str,
        default="",
    )
    parser.add_argument(
        "-m",
        "--mission-file",
        help="path to mission file being validated",
        type=str,
        default="",
    )
    parser.add_argument(
        "-d", "--drones", help="number of drones to simulate", type=int, default=1
    )
    parser.add_argument(
        "--lat", help="origin point latitude", type=float, default=DEFAULT_LAT
    )
    parser.add_argument(
        "--long", help="origin point longitude", type=float, default=DEFAULT_LONG
    )
    parser.add_argument(
        "-a", "--alt", help="origin point altitude", type=float, default=0.0
    )
    parser.add_argument(
        "-p",
        "--table-prefix",
        help="prefix for the waypoint value keys in the waypoint file",
        type=str,
        default="Hex",
    )
    args = parser.parse_args()

    validator = PathValidator(
        args.waypoint_file,
        args.mission_file,
        args.table_prefix,
        args.drones,
        args.lat,
        args.long,
        args.alt,
    )
    validator.parse_paths()
    validator.run_path(validator.path_list[0])

    render_test(validator.path_list[0])
    return 0


if __name__ == "__main__":
    sys.exit(main())
