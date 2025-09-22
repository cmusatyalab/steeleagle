import logging
from steeleagle_sdk.dsl import partition_geopoints     
from steeleagle_sdk.dsl.partitioner.survey import SurveyPartition
from steeleagle_sdk.dsl.partitioner.corridor import CorridorPartition
from steeleagle_sdk.dsl.partitioner.edge import EdgePartition
from steeleagle_sdk.dsl.partitioner.utils import parse_kml_file
from steeleagle_sdk.dsl.partitioner.visualize import visualize


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

kml_path = "./test_case.kml"
spacing = 5.0
angle = 0.0
trigger = 2

  
survey_partition = SurveyPartition(spacing=spacing, angle_degrees=angle, trigger_distance=trigger)
corridor_partition = CorridorPartition(spacing=spacing, angle_degrees=angle)
edge_partition = EdgePartition()
            
if __name__ == "__main__":
    try:
        raw_map = parse_kml_file(kml_path)
        geopoints_map = partition_geopoints(edge_partition, kml_path)
        visualize(raw_map, geopoints_map)
    except Exception as e :
        logger.info("something wrong %s", e)
