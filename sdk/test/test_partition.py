# # demo.py
# import logging
# from drone_partitioner import (
#     SurveyPartition, CorridorPartition, EdgePartition,
#     WaypointsUtils, get_partitioned_geopoints_map, GeoPoints
# )
# from drone_partitioner.visualize import visualize

# logging.basicConfig(level=logging.INFO)

# kml_path = "./example/fieldB.kml"
# spacing = 5.0
# angle = 0.0
# trigger = 10.0

# partition = SurveyPartition(spacing=spacing, angle_degrees=angle, trigger_distance=trigger)
# raw_map = WaypointsUtils.parse_kml_file(kml_path)
# part_map = get_partitioned_geopoints_map(partition, raw_map)

# polys = []
# paths = []
# for area, raw in raw_map.items():
#     poly_m = raw.convert_to_projected().to_polygon()
#     polys.append(poly_m)
#     for way in part_map.get(area, []):
#         paths.append(way.convert_to_projected())

# visualize(polys, paths)
