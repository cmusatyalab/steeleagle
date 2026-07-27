import xml.etree.ElementTree as ET
import os
import argparse
from steeleagle_protocol.v1.services.driver import control_pb2, control_pb2_grpc
from steeleagle_protocol.v1.services.mission import mission_pb2, mission_pb2_grpc
from steeleagle_protocol.v1.services.vehicle import data_pb2, data_pb2_grpc

def parse_kml_file(filename):
    ns = {'kml': 'http://www.opengis.net/kml/2.2'}
    tree = ET.parse('file.kml')
    root = tree.getroot()
    polygons = {}

    for placemark in root.iter('{http://www.opengis.net/kml/2.2}Placemark'):
        name_el = placemark.find('kml:name', ns)
        name = name_el.text if name_el is not None else 'Unnamed'
        for poly in placemark.iter('{http://www.opengis.net/kml/2.2}Polygon'):
            coords_el = poly.find('.//kml:coordinates', ns)
            if coords_el is not None:
                coords_text = coords_el.text.strip()
                points = coords_text.split()
                waypoints = []
                for p in points:
                    parts = p.split(',')
                    lon, lat = float(parts[0]), float(parts[1])
                    alt = float(parts[2]) if len(parts) > 2 else 0.0
                    waypoints.append((lat, lon, alt))
                polygons[name] = waypoints

    return polygons

class Mission(mission_pb2_grpc.MissionServiceServicer):
    """Mission servicer that will call successive GoToGlobalPosition commands.
    """
    def __init__(self, waypoints, client):
        self.waypoints = waypoints
        self.client = client

    def StartMission(self, request, context):
        for wp in self.waypoints:
            lat, lng, alt = wp
            req = control_pb2.GoToGlobalPositionRequest()
            req.position.latitude = lat
            req.position.longitude = lng
            req.position.altitude = alt
            try:
                resp = self.client.GoToGlobalPosition(req)
                # TODO: Wait until hover until next command
            except:
                return mission_pb2.StartMissionResponse()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="Basic Mission Module",
        description="Provides a simple mission module for testing purposes",
    )
    parser.add_argument(
        "-k",
        "--kml",
        required=True,
        help="Path to KML file to read waypoints from"
    )
    parser.add_argument(
        "-n",
        "--name",
        required=True,
        help="Name of the polygon to fly"
    )
    args = parser.parse_args()
    polygons = parse_kml_file(args.kml)

    if args.name not in polygons:
        raise ValueError(f"name {args.name} not in polygons: {polygons}")

    client_socket = os.getenv("CLIENT_SOCKET")
    if not client_socket:
        raise ValueError("client socket was None, aborting")
    listen_socket = os.getenv("LISTEN_SOCKET")
    if not listen_socket:
        raise ValueError("listen socket was None, aborting")
    client_socket = f"unix://{client_socket}"
    listen_socket = f"unix://{listen_socket}"
    mission = Mission(polygons[args.name], client_socket)
    server = grpc.Server(

    )
    mission_pb2_grpc.add_MissionServiceServicer_to_server(mission)
    server.add_insecure_port(listen_socket)
    server.start()
    server.wait_for_termination()
