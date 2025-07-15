from gabriel_server.network_engine import engine_runner
from sensor_twin_engine import SensorTwinEngine
import logging
import argparse
from utils.utils import setup_logging

SOURCE = 'openscout'

logger = logging.getLogger(__name__)

def main():
    setup_logging(logger)
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "-p", "--port", type=int, default=9099, help="Set port number"
    )

    parser.add_argument(
        "-r", "--threshold", type=float, default=0.85, help="Confidence threshold"
    )

    parser.add_argument(
        "-s", "--store", action="store_true", default=False, help="Store images with bounding boxes"
    )

    parser.add_argument(
        "-g", "--gabriel", default="tcp://gabriel-server:5555", help="Gabriel server endpoint"
    )

    parser.add_argument(
        "-src", "--source", default=SOURCE, help="Source for engine to register with"
    )

    parser.add_argument(
        "-x", "--exclude", help="Comma separated list of classes (ids) to exclude when peforming detection. Consult model/<model_name>/label_map.pbtxt"
    )

    # TODO verify need for this - might instead simply prefer path to initialization file
    parser.add_argument(
        "-d", "--drone", default="anafi", help="Drone model ([anafi, usa]). Used to define HFOV and VFOV for camera"
    )

    parser.add_argument(
        "-R", "--redis", type=int, default=6379, help="Set port number for redis connection [default: 6379]"
    )

    parser.add_argument(
        "-a", "--auth", default="", help="Share key for redis user"
    )

    parser.add_argument(
        "--radius", type=float, default=5.0, help="Radius in meters to consider when looking for previously found objects"
    )

    parser.add_argument(
        "--ttl", type=int, default=1200, help="TTL in seconds before objects are cleaned up in redis [default: 1200]"
    )

    parser.add_argument(
        "--geofence", default="geofence.kml", help="Path to KML file on the shared volume that specified the geofence [default: geofence.kml]"
    )

    parser.add_argument(
        "--geofence_enabled", action="store_true", default=False, help="Wheter to use a geofence to decide whether to store detections"
    )

    args, _ = parser.parse_known_args()

    def st_engine_setup():
        engine = SensorTwinEngine(args)

    logger.info("Starting SensorTwin engine...")
    engine_runner.run(engine=st_engine_setup(), source_name=args.source, server_address=args.gabriel, all_responses_required=True)

if __name__ == "__main__":
    main()