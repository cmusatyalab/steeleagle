import grpc
import threading
import time
import xml.etree.ElementTree as ET
import os
import argparse
from concurrent import futures
from steeleagle_protocol.v1.services.driver import control_pb2, control_pb2_grpc
from steeleagle_protocol.v1.services.mission import mission_pb2, mission_pb2_grpc
from steeleagle_protocol.v1.services.vehicle import data_pb2, data_pb2_grpc
from steeleagle_protocol.v1.messages.telemetry import telemetry_pb2

ALTITUDE = 20.0

def parse_kml_file(filename):
    ns = {'kml': 'http://www.opengis.net/kml/2.2'}
    tree = ET.parse(filename)
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
    def __init__(self, waypoints, control_client, data_client):
        self.waypoints = waypoints
        self.control_client = control_client
        self.data_client = data_client
        self.worker = None

    def waypoint_worker(self):
        for wp in self.waypoints:
            lat, lng, _ = wp
            req = control_pb2.GoToGlobalPositionRequest()
            req.position.latitude = lat
            req.position.longitude = lng
            req.position.altitude = ALTITUDE
            try:
                resp = self.control_client.GoToGlobalPosition(req)
                print(f'transiting to waypoint {lat}, {lng}')
                started_transit = False
                arrived = False
                while not arrived:
                    print(f'waiting to arrive')
                    try:
                        resp = self.data_client.GetTelemetry(data_pb2.GetTelemetryRequest())
                        motion_status = resp.telemetry.position_info.motion_status
                        if motion_status == telemetry_pb2.PositionInfo.MOTION_STATUS_IN_TRANSIT:
                            started_transit = True
                        elif started_transit and motion_status == telemetry_pb2.PositionInfo.MOTION_STATUS_HOLDING:
                            arrived = True
                        time.sleep(0.2)
                    except Exception as e:
                        print(f'got exception {e}')
            except Exception as e:
                print(f'got outer exception {e}')
                return

    def StartMission(self, request, context):
        self.worker = threading.Thread(target=self.waypoint_worker)
        self.worker.start()
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
    channel = grpc.insecure_channel(client_socket)
    control_client = control_pb2_grpc.ControlServiceStub(channel)
    data_client = data_pb2_grpc.DataServiceStub(channel)
    mission = Mission(polygons[args.name], control_client, data_client)
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    mission_pb2_grpc.add_MissionServiceServicer_to_server(mission, server)
    server.add_insecure_port(listen_socket)
    server.start()
    server.wait_for_termination()
