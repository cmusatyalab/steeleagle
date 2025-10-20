import airspace_region as asr
import geohash as pgh
from typing import Optional
import itertools
import time
from functools import wraps

import logging
from logger_config import AirspaceLoggerAdapter


BASE_TIMEOUT = 10  # in seconds

logger = logging.getLogger("airspace.engine")
actions_logger = logging.getLogger("airspace.actions")


class AirspaceControlEngine:
    def __init__(
        self,
        region_corners: list[tuple[float, float]],
        lat_partitions,
        lon_partitions,
        alt_partitions,
        min_alt,
        max_alt,
    ):
        self.next_common_id = 0
        self.drone_region_map = {}  # drone_id -> region
        self.drone_priority_map = {}  # drone_id -> priority
        self.region_map : dict[str, asr.AirspaceRegion] = {} # region_id (geohash) -> region object

        # Geohash precision and altitude descretization (can be adjusted based on expected region sizes)
        self.geohash_precision = 10
        self.altitude_precision = 5

        self.boundary_corners = region_corners

        self.create_airspace(
            region_corners,
            min_alt,
            max_alt,
            alt_partitions,
            lat_partitions,
            lon_partitions,
        )

        logger.info(
            f"AirspaceControlEngine initialized with geohash precision {self.geohash_precision}, altitude precision {self.altitude_precision}m"
        )

    def create_geohash_key(self, lat: float, lon: float, alt: float) -> str:
        """Create a 2D geohash key with altitude suffix (helps avoid colisions)"""

        base_geohash = pgh.encode(lat, lon, precision=self.geohash_precision)
        alt_discrete = int(alt / self.altitude_precision)

        return f"{base_geohash}_{alt_discrete}"

    def parse_geohash_key(self, geohash_key: str) -> tuple[str, int]:
        """Parse region ID into geohash and altitude"""

        if "_" in geohash_key:
            base_geohash, alt_str = geohash_key.rsplit("_", 1)
            alt_discrete = int(alt_str)
        else:
            base_geohash = geohash_key
            alt_discrete = 0
        return base_geohash, alt_discrete

    def _get_geohash_neighbors(self, geohash_key: str, search_radius: int = 1) -> list[str]:
        """Get neighboring geohashes including altitude variations"""
        base_geohash, ref_alt = self.parse_geohash_key(geohash_key)
        
        neighbor_keys = set()
        
        # Get 2D geohash neighbors
        current_geohashes = {base_geohash}
        
        # Expand outward by search_radius steps
        for radius in range(search_radius):
            next_geohashes = set()
            for gh in current_geohashes:
                neighbors_dict = pgh.neighbors(gh)
                next_geohashes.update(neighbors_dict)
            current_geohashes.update(next_geohashes)
        
        # Add altitude variations for each 2D neighbor
        for gh in current_geohashes:
            for alt_offset in range(-search_radius, search_radius + 1):
                neighbor_alt = ref_alt + alt_offset
                neighbor_key = f"{gh}_{neighbor_alt}"
                neighbor_keys.add(neighbor_key)
        
        return list(neighbor_keys)
    
    def add_region_airspace_map(self, region: asr.AirspaceRegion):
        centroid = region.get_centroid()
        lat, lon, alt = centroid

        geohash_id = self.create_geohash_key(lat, lon, alt)

        region.set_id(geohash_id)
        self.region_map[geohash_id] = region

        logger.info(
            f"c_id: {region.c_id} >> Added region {geohash_id} to airspace map at centroid ({lat:.4f}, {lon:.4f}, {alt:.0f})"
        )
        return geohash_id

    def get_next_cid(self):
        next_id = self.next_common_id
        self.next_common_id += 1
        return next_id

    def get_region_from_point(
        self, lat: float, lon: float, alt: float
    ) -> Optional[asr.AirspaceRegion]:
        logger.info(
            f"Searching for region containing point ({lat:.4f}, {lon:.4f}, {alt:.0f})"
        )
        geohash_key = self.create_geohash_key(lat, lon, alt)

        # Try exact match first
        if geohash_key in self.region_map:
            region = self.region_map[geohash_key]
            if region.contains(lat, lon, alt):
                logger.info(
                    f"c_id: {region.c_id} >> Region contains point ({lat:.4f}, {lon:.4f}, {alt:.0f})"
                )
                return region
            
        neighbor_keys = self._get_geohash_neighbors(geohash_key, search_radius=2)
        # If no exact match, search nearby geohashes
        for neighbor_key in neighbor_keys:
            if neighbor_key in self.region_map:
                region = self.region_map[neighbor_key]
                if region.contains(lat, lon, alt):
                    logger.info(
                    f"c_id: {region.c_id} >> Region contains point ({lat:.4f}, {lon:.4f}, {alt:.0f})"
                )
                    return region
        
        for region in self.region_map.values():
            if region.contains(lat, lon, alt):
                logger.info(
                    f"c_id: {region.c_id} >> Region contains point ({lat:.4f}, {lon:.4f}, {alt:.0f})"
                )
                return region
                
        return None

    def get_region_from_id(self, region_id: str) -> Optional[asr.AirspaceRegion]:
        region = self.region_map[region_id]
        if region is None:
            logger.warning(f"Region {region_id} not found in airspace map")
        return region

    # Point Organization Convetion: (lat, lon, alt)
    # Corner Ordering Convention: Top left -> Bottom left -> Bottom right -> Top right, Upper to Lower
    def create_airspace(
        self,
        grid_corners: list[tuple[float, float]],
        min_alt: float,
        max_alt: float,
        alt_partitions: int,
        lat_partitions: int,
        lon_partitions: int,
    ):
        logger.info(
            f"Creating airspace: {alt_partitions}×{lat_partitions}×{lon_partitions} grid, "
            f"altitude {min_alt}<->{max_alt}m, corners: {grid_corners}"
        )

        base_region = asr.AirspaceRegion(min_alt, max_alt, grid_corners, self.get_next_cid())
        self.boundary_corners = grid_corners
        final_regions = []
        lon_regions = []
        alt_regions = self.split_by_altitude(base_region, alt_partitions, is_set_up=True)

        for _, alt_region in enumerate(alt_regions):
            lon_regions = self.split_by_longitude(alt_region, lon_partitions, is_set_up=True)
            lon_level = []

            for _, lon_region in enumerate(lon_regions):
                lat_regions = self.split_by_latitude(
                    lon_region, lat_partitions, is_set_up=True
                )
                lon_level.append(lat_regions)

            final_regions.append(lon_level)

        self.establish_base_neighbors(
            final_regions, alt_partitions, lat_partitions, lon_partitions
        )

        total_regions = len(self.region_map)
        expected_regions = alt_partitions * lat_partitions * lon_partitions

        if total_regions != expected_regions:
            logger.error(
                f"Airspace creation mismatch: expected {expected_regions} regions, got {total_regions}"
            )
        else:
            logger.info(f"Airspace created successfully with {total_regions} regions")

        actions_logger.info(
            f"Airspace initialized with {total_regions} regions covering {min_alt}-{max_alt}m altitude"
        )

    def split_by_latitude(
        self, target_region: asr.AirspaceRegion, num_segments: int, is_set_up: bool
    ) -> list[asr.AirspaceRegion]:
        if num_segments <= 1:
            self.add_region_airspace_map(target_region)
            return [target_region]

        min_lat, max_lat = target_region.min_lat, target_region.max_lat
        min_lon, max_lon = target_region.min_lon, target_region.max_lon
        min_alt, max_alt = target_region.min_alt, target_region.max_alt

        step = (max_lat - min_lat) / num_segments
        regions = []

        logger.info(f"c_id: {target_region.c_id} >> Splitting by latitude into {num_segments} segments")

        for i in range(num_segments):
            segment_min_lat = min_lat + i * step
            segment_max_lat = min_lat + (i + 1) * step

            # Top left -> Bottom left -> Bottom right -> Top right, Upper to Lower
            new_corners = [
                (segment_max_lat, min_lon),
                (segment_min_lat, min_lon),
                (segment_min_lat, max_lon),
                (segment_max_lat, max_lon),
            ]

            new_region = asr.AirspaceRegion(min_alt, max_alt, new_corners, self.get_next_cid())
            regions.append(new_region)

            if is_set_up:
                self.add_region_airspace_map(new_region)
                
        if not is_set_up:
            self.establish_new_neighbors_lat_split(target_region, regions)

        return regions

    def split_by_longitude(
        self, target_region: asr.AirspaceRegion, num_segments: int, is_set_up:bool
    ) -> list[asr.AirspaceRegion]:
        if num_segments <= 1:
            return [target_region]

        min_lat, max_lat = target_region.min_lat, target_region.max_lat
        min_lon, max_lon = target_region.min_lon, target_region.max_lon
        min_alt, max_alt = target_region.min_alt, target_region.max_alt

        step = (max_lon - min_lon) / num_segments
        regions: list[asr.AirspaceRegion] = []

        logger.info(f"c_id: {target_region.c_id} >> Splitting by longitude into {num_segments} segments")

        for i in range(num_segments):
            segment_min_lon = min_lon + i * step
            segment_max_lon = min_lon + (i + 1) * step

            # Top left -> Bottom left -> Bottom right -> Top right, Upper to Lower
            new_corners = [
                (max_lat, segment_min_lon),
                (min_lat, segment_min_lon),
                (min_lat, segment_max_lon),
                (max_lat, segment_max_lon),
            ]

            new_region = asr.AirspaceRegion(min_alt, max_alt, new_corners, self.get_next_cid())
            regions.append(new_region)
        if not is_set_up:
            self.establish_new_neighbors_lon_split(target_region, regions)
        return regions

    def split_by_altitude(
        self, target_region: asr.AirspaceRegion, num_segments: int, is_set_up:bool
    ) -> list[asr.AirspaceRegion]:
        if num_segments <= 1:
            return [target_region]

        min_alt, max_alt = target_region.min_alt, target_region.max_alt
        corners = target_region.corners

        step = (max_alt - min_alt) / num_segments
        regions: list[asr.AirspaceRegion] = []

        logger.info(f"c_id: {target_region.c_id} >> Splitting by altitude into {num_segments} segments")

        for i in range(num_segments):
            segment_min_alt = min_alt + i * step
            segment_max_alt = min_alt + (i + 1) * step

            new_region = asr.AirspaceRegion(segment_min_alt, segment_max_alt, corners, self.get_next_cid())
            regions.append(new_region)
        
        if not is_set_up:
            self.establish_new_neighbors_alt_split(target_region, regions)
        return regions
    
    def establish_base_neighbors(
        self,
        regions: list[list[list[asr.AirspaceRegion]]],
        alt_partitions: int,
        lat_partitions: int,
        lon_partitions: int,
    ):
        logger.info(
            f"Establishing initial neighbor relationships for {alt_partitions}×{lat_partitions}×{lon_partitions} grid"
        )

        signs = [-1, 0, 1]
        neighbor_count = 0

        for alt in range(alt_partitions):
            for lon in range(lon_partitions):
                for lat in range(lon_partitions):
                    current_region = regions[alt][lon][lat]
                    region_neighbors = 0
                    # add neighbors
                    for combination in itertools.product(signs, repeat=3):
                        i, j, k = combination
                        try:
                            neighbor = regions[alt + i][lon + j][lat + k]
                            if i == 1:
                                current_region.add_upper_neighbor(neighbor.region_id)
                                region_neighbors += 1
                            elif i == -1:
                                current_region.add_lower_neighbor(neighbor.region_id)
                                region_neighbors += 1
                            elif (i, j, k) != (0, 0, 0):
                                # dont add self to neighbors
                                current_region.add_lateral_neighbor(neighbor.region_id)
                                region_neighbors += 1
                        except IndexError:
                            pass
                    neighbor_count += region_neighbors
        logger.info(f"Established {neighbor_count} neighbor relationships")

    def establish_new_neighbors_alt_split(
            self, 
            target_region: asr.AirspaceRegion, 
            sub_regions: list[asr.AirspaceRegion]):
        
        target_region_id = target_region.region_id
        old_lat_neighbors = target_region.lateral_neighbors
        old_upper_neighbors = target_region.upper_neighbors
        old_lower_neighbors = target_region.lower_neighbors

        for idx, new_region in enumerate(sub_regions):
            new_region_id = self.add_region_airspace_map(new_region)
            for lat_neighbor_id in old_lat_neighbors:
                new_region.add_lateral_neighbor(lat_neighbor_id)
                lat_neighbor = self.region_map[lat_neighbor_id]
                if idx == 0:
                    #only need to remove the original region from neighbors once 
                    lat_neighbor.remove_lateral_neighbor(target_region.region_id)
                lat_neighbor.add_lateral_neighbor(new_region_id)
            if idx == 0 :
                #bottom of the altsplit
                for lower_neighbor_id in old_lower_neighbors:
                    #cannot add this guy's upper neighbor yet (has not been assigned region's ID)
                    new_region.add_lower_neighbor(lower_neighbor_id)
                    lower_neighbor = self.region_map[lower_neighbor_id]
                    lower_neighbor.remove_upper_neighbor(target_region_id)
                    lower_neighbor.add_upper_neighbor(new_region_id)
            elif idx == len(sub_regions) -1:
                #top of the altsplit
                for upper_neighbor_id in old_upper_neighbors:
                    new_region.add_upper_neighbor(upper_neighbor_id)
                    new_region.add_lower_neighbor(sub_regions[idx-1].region_id)
                    upper_neighbor = self.region_map[upper_neighbor_id]
                    upper_neighbor.remove_lower_neighbor(target_region_id)
                    upper_neighbor.add_lower_neighbor(new_region_id)
            else:
                #middle of altsplit
                lower_neighbor = sub_regions[idx-1]
                lower_neighbor_id = lower_neighbor.region_id
                new_region.add_lower_neighbor(lower_neighbor_id)
                lower_neighbor.add_upper_neighbor(new_region_id)

        del self.region_map[target_region_id]

    def establish_new_neighbors_lon_split(
            self, 
            target_region: asr.AirspaceRegion, 
            sub_regions: list[asr.AirspaceRegion]):
        
        target_region_id = target_region.region_id
        old_lat_neighbors = self.get_directional_neighbors(target_region)
        old_upper_neighbors = target_region.upper_neighbors
        old_lower_neighbors = target_region.lower_neighbors

        for idx, new_region in enumerate(sub_regions):
            new_region_id = self.add_region_airspace_map(new_region)

            #all inherit vertical neighbors
            for upper_neighbor_id in old_upper_neighbors:
                upper_neighbor = self.region_map[upper_neighbor_id]
                if idx == 0:
                    upper_neighbor.remove_lower_neighbor(target_region_id)
                upper_neighbor.add_lower_neighbor(new_region_id)
                new_region.add_upper_neighbor(upper_neighbor_id)
            for lower_neighbor_id in old_lower_neighbors:
                lower_neighbor = self.region_map[lower_neighbor_id]
                if idx == 0:
                    lower_neighbor.remove_upper_neighbor(target_region_id)
                lower_neighbor.add_upper_neighbor(new_region_id)
                new_region.add_lower_neighbor(lower_neighbor_id)
            #all inherit north and south neighbors
            for direction in ['n', 's']:
                if old_lat_neighbors[direction] is not None:
                    neighbor_id = old_lat_neighbors[direction]
                    neighbor = self.region_map[neighbor_id]
                    if idx == 0:
                        neighbor.remove_lateral_neighbor(target_region_id)
                    neighbor.add_lateral_neighbor(new_region_id)
                    new_region.add_lateral_neighbor(neighbor_id)

            if idx == 0:
                #far west of lonsplit - needs to have south-west, west, north-west lat neighbors
                for direction in ['w', 'sw', 'nw']:
                    if old_lat_neighbors[direction] is not None:
                        neighbor_id = old_lat_neighbors[direction]
                        neighbor = self.region_map[neighbor_id]
                        neighbor.remove_lateral_neighbor(target_region_id)
                        neighbor.add_lateral_neighbor(new_region_id)
                        new_region.add_lateral_neighbor(neighbor_id)

            elif idx == len(sub_regions) - 1:
                #far east of lonsplit - needs to have north-east, east, south-east lat neighbors & previous from regions
                for direction in ['ne', 'se', 'e']:
                    if old_lat_neighbors[direction] is not None:
                        neighbor_id = old_lat_neighbors[direction]
                        neighbor = self.region_map[neighbor_id]
                        neighbor.remove_lateral_neighbor(target_region_id)
                        neighbor.add_lateral_neighbor(new_region_id)
                        new_region.add_lateral_neighbor(neighbor_id)
                new_region.add_lateral_neighbor(sub_regions[idx-1].region_id)
                sub_regions[idx-1].add_lateral_neighbor(new_region_id)
            else: 
                #add previous as lateral neighbor & vise versa 
                sub_regions[idx-1].add_lateral_neighbor(new_region_id)
                new_region.add_lateral_neighbor(sub_regions[idx-1].region_id)
            
        del self.region_map[target_region_id]
    
    def establish_new_neighbors_lat_split(
            self,
            target_region: asr.AirspaceRegion, 
            sub_regions: list[asr.AirspaceRegion]):
        
        target_region_id = target_region.region_id
        old_lat_neighbors = self.get_directional_neighbors(target_region)
        old_upper_neighbors = target_region.upper_neighbors
        old_lower_neighbors = target_region.lower_neighbors

        for idx, new_region in enumerate(sub_regions):
            new_region_id = self.add_region_airspace_map(new_region)

            #all inherit vertical neighbors
            for upper_neighbor_id in old_upper_neighbors:
                upper_neighbor = self.region_map[upper_neighbor_id]
                if idx == 0:
                    upper_neighbor.remove_lower_neighbor(target_region_id)
                upper_neighbor.add_lower_neighbor(new_region_id)
                new_region.add_upper_neighbor(upper_neighbor_id)
            for lower_neighbor_id in old_lower_neighbors:
                lower_neighbor = self.region_map[lower_neighbor_id]
                if idx == 0:
                    lower_neighbor.remove_upper_neighbor(target_region_id)
                lower_neighbor.add_upper_neighbor(new_region_id)
                new_region.add_lower_neighbor(lower_neighbor_id)
            #all inherit east and west neighbors
            for direction in ['e', 'w']:
                if old_lat_neighbors[direction] is not None:
                   neighbor_id = old_lat_neighbors[direction]
                   neighbor = self.region_map[neighbor_id]
                   neighbor.add_lateral_neighbor(new_region_id)
                   new_region.add_lateral_neighbor(neighbor_id)
                   if idx == 0:
                       neighbor.remove_lateral_neighbor(target_region_id)
        
            if idx == 0:
                #far south of lonsplit - needs to have south, south-west, south-east lat neighbors
                for direction in ['s', 'sw', 'se']:
                    if old_lat_neighbors[direction] is not None:
                        neighbor_id = old_lat_neighbors[direction]
                        neighbor = self.region_map[neighbor_id]
                        neighbor.remove_lateral_neighbor(target_region_id)
                        neighbor.add_lateral_neighbor(new_region_id)
                        new_region.add_lateral_neighbor(neighbor_id)

            elif idx == len(sub_regions) - 1:
                #far north of lonsplit - needs to have north, north-west, north-east lat neighbors & previous from regions
                for direction in ['n', 'nw', 'ne']:
                    if old_lat_neighbors[direction] is not None:
                        neighbor_id = old_lat_neighbors[direction]
                        neighbor = self.region_map[neighbor_id]
                        neighbor.remove_lateral_neighbor(target_region_id)
                        neighbor.add_lateral_neighbor(new_region_id)
                        new_region.add_lateral_neighbor(neighbor_id)
                new_region.add_lateral_neighbor(sub_regions[idx-1].region_id)
                sub_regions[idx-1].add_lateral_neighbor(new_region_id)
            else: 
                #add previous as lateral neighbor & vise versa 
                sub_regions[idx-1].add_lateral_neighbor(new_region_id)
                new_region.add_lateral_neighbor(sub_regions[idx-1].region_id)
            
        del self.region_map[target_region_id]

    def get_directional_neighbors(self, region: asr.AirspaceRegion) -> dict[str, str | None]:
        neighbors = {
            'n': None, 's': None, 'e': None, 'w': None,
            'ne': None, 'nw': None, 'se': None, 'sw': None
        }
        
        for neighbor_id in region.lateral_neighbors:
            neighbor = self.region_map[neighbor_id]
            
            # Check latitude relationship
            is_north = abs(neighbor.min_lat - region.max_lat) < 1e-9
            is_south = abs(neighbor.max_lat - region.min_lat) < 1e-9
            lat_aligned = abs(neighbor.min_lat - region.min_lat) < 1e-9 and \
                        abs(neighbor.max_lat - region.max_lat) < 1e-9
            
            # Check longitude relationship
            is_east = abs(neighbor.min_lon - region.max_lon) < 1e-9
            is_west = abs(neighbor.max_lon - region.min_lon) < 1e-9
            lon_aligned = abs(neighbor.min_lon - region.min_lon) < 1e-9 and \
                        abs(neighbor.max_lon - region.max_lon) < 1e-9
            
            # Categorize
            if is_north and lon_aligned:
                neighbors['n'] = neighbor_id
            elif is_south and lon_aligned:
                neighbors['s'] = neighbor_id
            elif is_east and lat_aligned:
                neighbors['e'] = neighbor_id
            elif is_west and lat_aligned:
                neighbors['w'] = neighbor_id
            elif is_north and is_east:
                neighbors['ne'] = neighbor_id
            elif is_north and is_west:
                neighbors['nw'] = neighbor_id
            elif is_south and is_east:
                neighbors['se'] = neighbor_id
            elif is_south and is_west:
                neighbors['sw'] = neighbor_id
        
        return neighbors       

    def reserve_region(self, drone_id, target_region: asr.AirspaceRegion) -> bool:
        region_adapter = AirspaceLoggerAdapter(
            logger, {"drone_id": drone_id, "region_id": target_region.region_id}
        )

        if not target_region.is_available():
            # Renew the lease if already owned by the requesting drone
            curr_owner = target_region.get_owner()
            if curr_owner is not None and curr_owner == drone_id:
                region_adapter.info(f"c_id: {target_region.c_id} >> Renewed lease for existing reservation")
                target_region.set_timeout(BASE_TIMEOUT)
                return True
            # Fail if owned by another drone
            actions_logger.warning(
                f"c_id: {target_region.c_id} >> RESERVATION CONFLICT: Drone {drone_id} attempted to reserve region {target_region.region_id} owned by drone {curr_owner}"
            )
            region_adapter.warning(
                f"c_id: {target_region.c_id} >> RESERVATION DENIED: Region owned by drone {curr_owner}"
            )
            return False

        region_adapter.info(
            f"c_id: {target_region.c_id} >> Region reserved successfully (priority: {self.drone_priority_map.get(drone_id, 'unknown')})"
        )
        target_region.update_status(asr.RegionStatus.ALLOCATED)
        target_region.update_owner(drone_id, self.drone_priority_map[drone_id])
        return True

    def renew_region(self, drone_id, target_region: asr.AirspaceRegion) -> bool:
        region_adapter = AirspaceLoggerAdapter(
            logger, {"drone_id": drone_id, "region_id": target_region.region_id}
        )
        region_stat = target_region.get_status()
        if (
            region_stat is asr.RegionStatus.NOFLY
            or region_stat is asr.RegionStatus.FREE
        ):
            region_adapter.warning(
                f"c_id: {target_region.c_id} >> RENEWAL DENIED - region status: {region_stat.name}"
            )
            return False
        curr_owner = target_region.get_owner()
        if curr_owner is not None and curr_owner == drone_id:
            region_adapter.info(f"Lease renewed")
            target_region.set_timeout(BASE_TIMEOUT)
            return True

        actions_logger.warning(
            f"c_id: {target_region.c_id} >> UNAUTHORIZED RENEWAL: Drone {drone_id} attempted to renew region {target_region.region_id} owned by drone {curr_owner}"
        )
        return False

    # needs to be async
    def revoke_region(self, target_region: asr.AirspaceRegion) -> bool:
        logger.warning(
            f"c_id: {target_region.c_id} >> Region {target_region.region_id} revocation requested (owner: {target_region.get_owner()})"
        )
        actions_logger.warning(
            f"c_id: {target_region.c_id} >> REGION REVOCATION: {target_region.region_id} revoked from drone {target_region.get_owner()}"
        )
        return True

    def query_region(
        self, target_region: asr.AirspaceRegion
    ) -> tuple[asr.RegionStatus, int | None, int | None]:
        region_status = target_region.get_status()
        region_owner = target_region.get_owner()
        region_priority = target_region.get_priority()
        return (region_status, region_owner, region_priority)

    def query_lateral_neighbors(
        self, ref_region: asr.AirspaceRegion
    ) -> list[tuple[bool, int | None]]:
        neighbor_info = list()
        for neighbor_id in ref_region.lateral_neighbors:
            neighbor_region = self.region_map[neighbor_id]
            neighbor_status = neighbor_region.get_status()
            if neighbor_status in [asr.RegionStatus.OCCUPIED, asr.RegionStatus.RESTRICTED_OCCUPIED]:
                neighbor_occupant = neighbor_region.get_owner()
            else: 
                neighbor_occupant = None
            neighbor_info.append((neighbor_status, neighbor_occupant))

        return neighbor_info

    def query_upper_neighbors(
        self, ref_region: asr.AirspaceRegion
    ) -> list[tuple[bool, int]]:
        neighbor_info = list()
        for neighbor_id in ref_region.upper_neighbors:
            neighbor_region = self.region_map[neighbor_id]
            neighbor_status = neighbor_region.get_status()
            if neighbor_status in [asr.RegionStatus.OCCUPIED, asr.RegionStatus.RESTRICTED_OCCUPIED]:
                neighbor_occupant = neighbor_region.get_owner()
            else: 
                neighbor_occupant = None
            neighbor_info.append((neighbor_status, neighbor_occupant))

        return neighbor_info

    def query_lower_neighbors(
        self, ref_region: asr.AirspaceRegion
    ) -> list[tuple[bool, int]]:
        neighbor_info = list()
        for neighbor_id in ref_region.lower_neighbors:
            neighbor_region = self.region_map[neighbor_id]
            neighbor_status = neighbor_region.get_status()
            if neighbor_status in [asr.RegionStatus.OCCUPIED, asr.RegionStatus.RESTRICTED_OCCUPIED]:
                neighbor_occupant = neighbor_region.get_owner()
            else: 
                neighbor_occupant = None
            neighbor_info.append((neighbor_status, neighbor_occupant))

        return neighbor_info

    def set_priority(self, drone_id: int, new_priority: int):
        old_priority = self.drone_priority_map.get(drone_id)
        self.drone_priority_map[drone_id] = new_priority
        logger.info(
            f"Priority updated for drone {drone_id}: {old_priority} -> {new_priority}"
        )

    # needs to be async for if drone is currently in region/ region is reserved
    def mark_no_fly(self, target_region: asr.AirspaceRegion) -> bool:
        logger.critical(f"c_id: {target_region.c_id} >> NO-FLY ZONE established for region {target_region.region_id}")
        actions_logger.critical(
            f"c_id: {target_region.c_id} >> NO-FLY ZONE: Region {target_region.region_id} marked as no-fly (previous owner: {target_region.get_owner()})"
        )
        return True

    # needs to be async for if drone is currently in region/ region is reserved
    def mark_restricted_fly(self, target_region: asr.AirspaceRegion) -> bool:
        logger.warning(
            f"c_id: {target_region.c_id} >> RESTRICTED ZONE established for region {target_region.region_id}"
        )
        actions_logger.warning(
            f"c_id: {target_region.c_id} >> RESTRICTED ZONE: Region {target_region.region_id} marked as restricted"
        )
        return True

    def add_occupant(self, drone_id: int, target_region: asr.AirspaceRegion) -> bool:
        region_adapter = AirspaceLoggerAdapter(
            logger, {"drone_id": drone_id, "region_id": target_region.region_id}
        )

        region_status = target_region.get_status()
        region_owner = target_region.get_owner()
        if region_owner != drone_id:
            actions_logger.error(
                f"c_id: {target_region.c_id} >> UNAUTHORIZED OCCUPANCY: Drone {drone_id} attempted to occupy region {target_region.region_id} owned by drone {region_owner}"
            )
            region_adapter.error(
                f"c_id: {target_region.c_id} >> Occupancy denied - not region owner (owner: {region_owner})"
            )
            return False
        if region_status is asr.RegionStatus.RESTRICTED_ALLOCATED:
            region_adapter.info(f"c_id: {target_region.c_id} >> Entered restricted region")
            target_region.update_status(asr.RegionStatus.RESTRICTED_OCCUPIED)
            self.renew_region(drone_id, target_region)
            if drone_id in self.drone_region_map and self.drone_region_map[drone_id] != target_region:
                self.remove_occupant(drone_id, self.drone_region_map[drone_id])
                self.drone_region_map[drone_id] = target_region
            return True
        if region_status is asr.RegionStatus.ALLOCATED:
            region_adapter.info(f"c_id: {target_region.c_id} >> Entered region")
            target_region.update_status(asr.RegionStatus.OCCUPIED)
            self.renew_region(drone_id, target_region)
            if drone_id in self.drone_region_map and self.drone_region_map[drone_id] != target_region:
                self.remove_occupant(drone_id, self.drone_region_map[drone_id])
                self.drone_region_map[drone_id] = target_region
            return True
        region_adapter.error(
            f"Occupancy denied - invalid region status: {region_status.name}"
        )
        return False

    def remove_occupant(self, drone_id: int, target_region: asr.AirspaceRegion) -> bool:
        region_adapter = AirspaceLoggerAdapter(
            logger, {"drone_id": drone_id, "region_id": target_region.region_id}
        )

        region_status = target_region.get_status()
        region_owner = target_region.get_owner()
        if region_owner != drone_id:
            actions_logger.error(
                f"c_id: {target_region.c_id} >> UNAUTHORIZED EXIT: Drone {drone_id} attempted to exit region {target_region.region_id} owned by drone {region_owner}"
            )
            region_adapter.error(f"Exit denied - not region owner")
            return False
        if region_status is asr.RegionStatus.OCCUPIED:
            region_adapter.info(f"c_id: {target_region.c_id} >> Exited region")
            target_region.update_owner(None, None)
            target_region.update_status(asr.RegionStatus.FREE)
            target_region.clear_timeout()
            self.drone_region_map[drone_id] = None
            return True
        if region_status is asr.RegionStatus.RESTRICTED_OCCUPIED:
            region_adapter.info(f"c_id: {target_region.c_id} >> Exited restricted region")
            target_region.update_owner(None, None)
            target_region.update_status(asr.RegionStatus.RESTRICTED_AVAILABLE)
            target_region.clear_timeout()
            self.drone_region_map[drone_id] = None
            return True
        region_adapter.warning(
            f"Exit attempted from unoccupied region (status: {region_status.name})"
        )
        return False

    def validate_position(self, drone_id, lat, lon, alt):
        current_region = self.get_region_from_point(lat, lon, alt)
        if (current_region is not None) and (current_region.get_owner() == drone_id):
            last_region = self.drone_region_map[drone_id]
            if last_region.c_id != current_region.c_id:
                self.remove_occupant(drone_id, last_region)
                self.add_occupant(drone_id, current_region)
            return True
        else:
            if current_region is not None:
                actions_logger.warning(f"c_id: {current_region.c_id} >> Failed to validate occupant {drone_id}")
            else:
                actions_logger.warning(f"c_id: None >> Failed to validate occupant {drone_id}, "
                                       f"current location ({lat}, {lon}, {alt}) outside geohashed region")
            return False