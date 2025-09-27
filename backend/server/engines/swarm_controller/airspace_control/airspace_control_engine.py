import airspace_region as asr
import pygeohash as pgh
from typing import Optional
import itertools
import time
from functools import wraps

import logging
from logger_config import AirspaceLoggerAdapter


BASE_TIMEOUT = 10  # in seconds

logger = logging.getLogger('airspace.engine')
security_logger = logging.getLogger('airspace.security')


class AirspaceControlEngine:
    def __init__(self,
        region_corners: list[tuple[float, float]], lat_partitions, lon_partitions, alt_partitions, min_alt, max_alt):
        self.drone_region_map = {}  # drone_id -> region
        self.drone_priority_map = {}  # drone_id -> priority
        self.region_map = {} # region_id (geohash) -> region object
        
        #Geohash precision and altitude descretization (can be adjusted based on expected region sizes)
        self.geohash_precision = 8
        self.altitude_precision = 10

        self.boundary_corners = region_corners

        self.create_airspace(region_corners, min_alt, max_alt, alt_partitions, lat_partitions, lon_partitions)
        
        logger.info(f"AirspaceControlEngine initialized with geohash precision {self.geohash_precision}, altitude precision {self.altitude_precision}m")

    def create_geohash_key(self, lat: float, lon: float, alt: float) -> str: 
        '''Create a 2D geohash key with altitude suffix (helps avoid colisions)'''

        base_geohash = pgh.encode(lat, lon, precision=self.geohash_precision)
        alt_discrete = int(alt/self.altitude_precision)

        return f"{base_geohash}_{alt_discrete}"
    
    def parse_geohash_key(self, geohash_key: str) -> tuple[str, int]:
        """ Parse region ID into geohash and altitude """

        if '_' in geohash_key:
            base_geohash, alt_str = geohash_key.rsplit('_', 1)
            alt_discrete = int(alt_str)
        else: 
            base_geohash = geohash_key
            alt_discrete = 0
        return base_geohash, alt_discrete
    
    def add_region_airspace_map(self, region: asr.AirspaceRegion):
        centroid = region.get_centroid()
        lat, lon, alt = centroid

        geohash_id = self.create_geohash_key(lat, lon, alt)

        region.set_id(geohash_id) 
        self.region_map[geohash_id] = region

        logger.debug(f"Added region {geohash_id} to airspace map at centroid ({lat:.4f}, {lon:.4f}, {alt:.0f})")
        return geohash_id
    
    def get_region_from_point(self, lat: float, lon: float, alt: float) -> Optional[asr.AirspaceRegion]:
        logger.debug(f"Searching for region containing point ({lat:.4f}, {lon:.4f}, {alt:.0f})")
        geohash_key = self.create_geohash_key(lat, lon, alt)
        
        # Try exact match first
        if geohash_key in self.region_map:
            region = self.region_map[geohash_key]
            if region.contains(lat, lon, alt):
                return region

    def get_region_from_id(self, region_id:str) -> Optional[asr.AirspaceRegion]:
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
        logger.info(f"Creating airspace: {alt_partitions}×{lat_partitions}×{lon_partitions} grid, "
                   f"altitude {min_alt}-{max_alt}m, corners: {grid_corners}")
        
        base_region = asr.AirspaceRegion(min_alt, max_alt, grid_corners)
        self.boundary_corners = grid_corners
        final_regions = []
        lon_regions = []
        alt_regions = self.split_by_altitude(base_region, alt_partitions)

        for alt_idx, alt_region in enumerate(alt_regions):
            lon_regions = self.split_by_longitude(alt_region, lon_partitions)
            lon_level = []
            
            for lon_idx, lon_region in enumerate(lon_regions):
                lat_regions = self.split_by_latitude(lon_region, lat_partitions, is_set_up=True)
                lon_level.append(lat_regions)
            
            final_regions.append(lon_level)

        self.establish_base_neighbors(final_regions, alt_partitions, lat_partitions, lon_partitions)

        total_regions = len(self.region_map)
        expected_regions = alt_partitions * lat_partitions * lon_partitions
        
        if total_regions != expected_regions:
            logger.error(f"Airspace creation mismatch: expected {expected_regions} regions, got {total_regions}")
        else:
            logger.info(f"Airspace created successfully with {total_regions} regions")
            
        security_logger.info(f"Airspace initialized with {total_regions} regions covering {min_alt}-{max_alt}m altitude")

    def split_by_latitude(
        self, target_region: asr.AirspaceRegion, num_segments: int, is_set_up: bool
    ) -> list[asr.AirspaceRegion]:
        if num_segments <=1 : 
            return [target_region]
        
        min_lat, max_lat = target_region.min_lat, target_region.max_lat
        min_lon, max_lon = target_region.min_lon, target_region.max_lon
        min_alt, max_alt = target_region.min_alt, target_region.max_alt

        step = (max_lat - min_lat) / num_segments
        regions = []

        logger.debug(f"Splitting region by latitude into {num_segments} segments")

        for i in range(num_segments):
            segment_min_lat = min_lat + i *step
            segment_max_lat = max_lat + (i+1)*step

            # Top left -> Bottom left -> Bottom right -> Top right, Upper to Lower
            new_corners = [
                (segment_max_lat, min_lon),  
                (segment_min_lat, min_lon),  
                (segment_min_lat, max_lon),  
                (segment_max_lat, max_lon)
            ]

            new_region = asr.AirspaceRegion(min_alt, max_alt, new_corners)
            regions.append(new_region)
            
            if is_set_up:
                self.add_region_airspace_map(new_region)
                
        return regions
    
    def split_by_longitude(
        self, target_region: asr.AirspaceRegion, num_segments: int
    ) -> list[asr.AirspaceRegion]:
        
        if num_segments <=1 : 
            return [target_region]
        
        min_lat, max_lat = target_region.min_lat, target_region.max_lat
        min_lon, max_lon = target_region.min_lon, target_region.max_lon
        min_alt, max_alt = target_region.min_alt, target_region.max_alt

        step = (max_lon - min_lon) / num_segments
        regions = []

        logger.debug(f"Splitting region by longitude into {num_segments} segments")
        
        for i in range(num_segments):
            segment_min_lon = min_lon + i *step
            segment_max_lon = max_lon + (i+1)*step

            # Top left -> Bottom left -> Bottom right -> Top right, Upper to Lower
            new_corners = [
                (max_lat, segment_min_lon),
                (min_lat, segment_min_lon),
                (min_lat, segment_max_lon),
                (max_lat, segment_max_lon)
            ]

            new_region = asr.AirspaceRegion(min_alt, max_alt, new_corners)
            regions.append(new_region)

        return regions

    def split_by_altitude(
        self, target_region: asr.AirspaceRegion, num_segments: int
    ) -> list[asr.AirspaceRegion]:
        if num_segments <= 1:
            return [target_region]
        
        min_alt, max_alt = target_region.min_alt, target_region.max_alt
        corners = target_region.corners

        step = (max_alt - min_alt) /num_segments
        regions = []

        logger.debug(f"Splitting region by altitude into {num_segments} segments")

        for i in range(num_segments):
            segment_min_alt = min_alt + i*step
            segment_max_alt = max_alt + (i+1)*step

            new_region = asr.AirspaceRegion(segment_min_alt, segment_max_alt, corners)
            regions.append(new_region)
        return regions

    #establishing neighbor relationships
    def establish_base_neighbors(self, regions:list[list[list[asr.AirspaceRegion]]], alt_partitions: int, lat_partitions: int, lon_partitions: int):
        logger.debug(f"Establishing initial neighbor relationships for {alt_partitions}×{lat_partitions}×{lon_partitions} grid")
        
        signs = [-1,0,1]
        neighbor_count = 0

        for alt in range(alt_partitions):
            for lon in range(lon_partitions):
                for lat in range(lon_partitions):
                    current_region = regions[alt][lon][lat] 
                    region_neighbors = 0
                    #add neighbors
                    for combination in itertools.product(signs, repeat = 3):
                        i,j,k = combination
                        try:
                            neighbor = regions[alt+i][lon+j][lat+k]
                            if i == 1:
                                current_region.add_upper_neighbor(neighbor.region_id)
                                region_neighbors += 1
                            elif i == -1:
                                current_region.add_lower_neighbor(neighbor.region_id)
                                region_neighbors += 1
                            elif (i, j, k) != (0,0,0):
                                #dont add self to neighbors
                                current_region.add_lateral_neighbor(neighbor.region_id)
                                region_neighbors += 1
                        except IndexError: 
                            pass
                    neighbor_count += region_neighbors
        logger.debug(f"Established {neighbor_count} neighbor relationships")

    #need some methodology for further splitting regions and updating airspace map & neighbors

    def reserve_region(self, drone_id, target_region: asr.AirspaceRegion) -> bool:
        region_adapter = AirspaceLoggerAdapter(logger, {'drone_id': drone_id, 'region_id': target_region.region_id})

        if not target_region.is_available():
            # Renew the lease if already owned by the requesting drone
            curr_owner = target_region.get_owner()
            if curr_owner is not None and curr_owner == drone_id:
                region_adapter.info(f"Renewed lease for existing reservation")
                target_region.set_timeout(BASE_TIMEOUT)
                return True
            # Fail if owned by another drone
            security_logger.warning(f"RESERVATION CONFLICT: Drone {drone_id} attempted to reserve region {target_region.region_id} owned by drone {curr_owner}")
            region_adapter.warning(f"Reservation denied - region owned by drone {curr_owner}")
            return False
        
        region_adapter.info(f"Region reserved successfully (priority: {self.drone_priority_map.get(drone_id, 'unknown')})")
        target_region.update_status(asr.RegionStatus.ALLOCATED)
        target_region.update_owner(drone_id, self.drone_priority_map[drone_id])
        return True

    def renew_region(self, drone_id, target_region: asr.AirspaceRegion) -> bool:
        region_adapter = AirspaceLoggerAdapter(logger, {'drone_id': drone_id, 'region_id': target_region.region_id})
        region_stat = target_region.get_status()
        if (
            region_stat is asr.RegionStatus.NOFLY
            or region_stat is asr.RegionStatus.FREE
        ):
            region_adapter.warning(f"Renewal denied - region status: {region_stat.name}")
            return False
        curr_owner = target_region.get_owner()
        if curr_owner is not None and curr_owner == drone_id:
            region_adapter.info(f"Lease renewed")
            target_region.set_timeout(BASE_TIMEOUT)
            return True
        
        security_logger.warning(f"UNAUTHORIZED RENEWAL: Drone {drone_id} attempted to renew region {target_region.region_id} owned by drone {curr_owner}")
        return False

    # needs to be async
    def revoke_region(self, target_region: asr.AirspaceRegion) -> bool:
        logger.warning(f"Region {target_region.region_id} revocation requested (owner: {target_region.get_owner()})")
        security_logger.warning(f"REGION REVOCATION: {target_region.region_id} revoked from drone {target_region.get_owner()}")
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
    ) -> list[tuple[bool, int]]:
        return list()

    def query_upper_neighbors(
        self, ref_region: asr.AirspaceRegion
    ) -> list[tuple[bool, int]]:
        return list()

    def query_lower_neighbors(
        self, ref_region: asr.AirspaceRegion
    ) -> list[tuple[bool, int]]:
        return list()

    def set_priority(self, drone_id: int, new_priority: int):
        old_priority = self.drone_priority_map.get(drone_id)
        self.drone_priority_map[drone_id] = new_priority
        logger.info(f"Priority updated for drone {drone_id}: {old_priority} -> {new_priority}")

    # needs to be async for if drone is currently in region/ region is reserved
    def mark_no_fly(self, target_region: asr.AirspaceRegion) -> bool:
        logger.critical(f"NO-FLY ZONE established for region {target_region.region_id}")
        security_logger.critical(f"NO-FLY ZONE: Region {target_region.region_id} marked as no-fly (previous owner: {target_region.get_owner()})")
        return True

    # needs to be async for if drone is currently in region/ region is reserved
    def mark_restricted_fly(self, target_region: asr.AirspaceRegion) -> bool:
        logger.warning(f"RESTRICTED ZONE established for region {target_region.region_id}")
        security_logger.warning(f"RESTRICTED ZONE: Region {target_region.region_id} marked as restricted")
        return True

    def add_occupant(self, drone_id: int, target_region: asr.AirspaceRegion) -> bool:
        region_adapter = AirspaceLoggerAdapter(logger, {'drone_id': drone_id, 'region_id': target_region.region_id})

        region_status = target_region.get_status()
        region_owner = target_region.get_owner()
        if region_owner != drone_id:
            security_logger.error(f"UNAUTHORIZED OCCUPANCY: Drone {drone_id} attempted to occupy region {target_region.region_id} owned by drone {region_owner}")
            region_adapter.error(f"Occupancy denied - not region owner (owner: {region_owner})")
            return False
        if region_status is asr.RegionStatus.RESTRICTED_ALLOCATED:
            region_adapter.info(f"Entered restricted region")
            target_region.update_status(asr.RegionStatus.RESTRICTED_OCCUPIED)
            self.renew_region(drone_id, target_region)
            return True
        if region_status is asr.RegionStatus.ALLOCATED:
            region_adapter.info(f"Entered region")
            target_region.update_status(asr.RegionStatus.OCCUPIED)
            self.renew_region(drone_id, target_region)
            return True
        region_adapter.error(f"Occupancy denied - invalid region status: {region_status.name}")
        return False

    def remove_occupant(self, drone_id: int, target_region: asr.AirspaceRegion) -> bool:
        region_adapter = AirspaceLoggerAdapter(logger, {'drone_id': drone_id, 'region_id': target_region.region_id})

        region_status = target_region.get_status()
        region_owner = target_region.get_owner()
        if region_owner != drone_id:
            security_logger.error(f"UNAUTHORIZED EXIT: Drone {drone_id} attempted to exit region {target_region.region_id} owned by drone {region_owner}")
            region_adapter.error(f"Exit denied - not region owner")
            return False
        if region_status is asr.RegionStatus.OCCUPIED:
            region_adapter.info(f"Exited region")
            target_region.update_owner(None, None)
            target_region.update_status(asr.RegionStatus.FREE)
            target_region.clear_timeout()
            return True
        if region_owner is asr.RegionStatus.RESTRICTED_OCCUPIED:
            region_adapter.info(f"Exited restricted region")
            target_region.update_owner(None, None)
            target_region.update_status(asr.RegionStatus.RESTRICTED_AVAILABLE)
            target_region.clear_timeout()
            return True
        region_adapter.warning(f"Exit attempted from unoccupied region (status: {region_status.name})")
        return False
