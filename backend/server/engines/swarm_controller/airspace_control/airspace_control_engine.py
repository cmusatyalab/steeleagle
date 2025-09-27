import airspace_region as asr
import pygeohash as pgh
from typing import Optional
import itertools


BASE_TIMEOUT = 10  # in seconds


class AirspaceControlEngine:
    def __init__(self, region_corners):
        self.drone_region_map = {}  # drone_id -> region
        self.drone_priority_map = {}  # drone_id -> priority
        self.region_map = {} # region_id (geohash) -> region object
        
        #Geohash precision and altitude descretization (can be adjusted based on expected region sizes)
        self.geohash_precision = 8
        self.altitude_precision = 10

        self.boundary_corners = region_corners

        self.create_airspace(region_corners)

    def _create_geohash_key(self, lat: float, lon: float, alt: float) -> str: 
        '''Create a 2D geohash key with altitude suffix (helps avoid colisions)'''

        base_geohash = pgh.encode(lat, lon, precision=self.geohash_precision)
        alt_discrete = int(alt/self.altitude_precision)

        return f"{base_geohash}_{alt_discrete}"
    
    def _parse_geohash_key(self, geohash_key: str) -> tuple[str, int]:
        """ Parse region ID into geohash and altitude """

        if '_' in geohash_key:
            base_geohash, alt_str = geohash_key.rsplit('_', 1)
            alt_discrete = int(alt_str)
        else: 
            base_geohash = geohash_key
            alt_discrete = 0
        return base_geohash, alt_discrete
    
    def _add_region_airspace_map(self, region: asr.AirspaceRegion):
        centroid = region.get_centroid
        lat, lon, alt = centroid

        geohash_id = self._create_geohash_key(lat, lon, alt)

        region.set_id(geohash_id) 
        self.region_map[geohash_id] = region

        return geohash_id
    
    def get_region_from_point(self, lat: float, lon: float, alt: float) -> Optional[asr.AirspaceRegion]:
        pass

    def get_region_from_id(self, region_id:str) -> Optional[asr.AirspaceRegion]:
        return self.region_map[region_id]
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
        base_region = asr.AirspaceRegion(min_alt, max_alt, grid_corners)
        self.boundary_corners = grid_corners
        final_regions = []
        lon_regions = []
        alt_regions = self.split_by_altitude(base_region, alt_partitions)
        for r in alt_regions:
            lon_regions.append(self.split_by_longitude(r, lon_partitions))
        # lon_regions : [alt_part][lon_part]
        for alt_split in lon_regions:
            for r in alt_split:
                final_regions.append(self.split_by_latitude(r, lat_partitions, is_set_up=True))
        #final regions : [alt_part][lon_part][lat_part]
        #regions are added to the map in split by latitude
        self.establish_base_neighbors(final_regions, alt_partitions, lat_partitions, lon_partitions)

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
                self._add_region_airspace_map(new_region)
                
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

        for i in range(num_segments):
            segment_min_alt = min_alt + i*step
            segment_max_alt = max_alt + (i+1)*step

            new_region = asr.AirspaceRegion(segment_min_alt, segment_max_alt, corners)
            regions.append(new_region)
        return regions

    #establishing neighbor relationships
    def establish_base_neighbors(self, regions:list[list[list[asr.AirspaceRegion]]], alt_partitions: int, lat_partitions: int, lon_partitions: int):
        #add neighbors if is initial splitting, should be semetric partitions so simple index logic to add neighbors
       # Neighbor maps for regions that share sides
        # Same altitude neighbors (x8)
        # Higher altitude neighbors (x9)
        # Lower altitude neighbors (x9)
        signs = [-1,0,1]
        for alt in range(alt_partitions):
            for lon in range(lon_partitions):
                for lat in range(lon_partitions):
                    current_region = regions[alt][lon][lat] 
                    #add neighbors
                    for combination in itertools.product(signs, repeat = 3):
                        i,j,k = combination
                        try:
                            neighbor = regions[alt+i][lon+j][lat+k]
                            if i == 1:
                                current_region.add_upper_neighbor(neighbor.region_id)
                            elif i == -1:
                                current_region.add_lower_neighbor(neighbor.region_id)
                            elif (i, j, k) != (0,0,0):
                                #dont add self to neighbors
                                current_region.add_lateral_neighbor(neighbor.region_id)
                        except IndexError: 
                            pass

    #need some methodology for further splitting regions and updating airspace map & neighbors

    def reserve_region(self, drone_id, target_region: asr.AirspaceRegion) -> bool:
        if not target_region.is_available():
            # Renew the lease if already owned by the requesting drone
            curr_owner = target_region.get_owner()
            if curr_owner is not None and curr_owner == drone_id:
                target_region.set_timeout(BASE_TIMEOUT)
                return True
            # Fail if owned by another drone
            return False
        target_region.update_status(asr.RegionStatus.ALLOCATED)
        target_region.update_owner(drone_id, self.drone_priority_map[drone_id])
        return True

    def renew_region(self, drone_id, target_region: asr.AirspaceRegion) -> bool:
        region_stat = target_region.get_status()
        if (
            region_stat is asr.RegionStatus.NOFLY
            or region_stat is asr.RegionStatus.FREE
        ):
            return False
        curr_owner = target_region.get_owner()
        if curr_owner is not None and curr_owner == drone_id:
            target_region.set_timeout(BASE_TIMEOUT)
            return True
        return False

    # needs to be async
    def revoke_region(self, target_region: asr.AirspaceRegion) -> bool:
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
        self.drone_priority_map[drone_id] = new_priority

    # needs to be async for if drone is currently in region/ region is reserved
    def mark_no_fly(self, target_region: asr.AirspaceRegion) -> bool:
        return True

    # needs to be async for if drone is currently in region/ region is reserved
    def mark_restricted_fly(self, target_region: asr.AirspaceRegion) -> bool:
        return True

    def add_occupant(self, drone_id: int, target_region: asr.AirspaceRegion) -> bool:
        region_status = target_region.get_status()
        region_owner = target_region.get_owner()
        if region_owner != drone_id:
            return False
        if region_status is asr.RegionStatus.RESTRICTED_ALLOCATED:
            target_region.update_status(asr.RegionStatus.RESTRICTED_OCCUPIED)
            self.renew_region(drone_id, target_region)
            return True
        if region_status is asr.RegionStatus.ALLOCATED:
            target_region.update_status(asr.RegionStatus.OCCUPIED)
            self.renew_region(drone_id, target_region)
            return True
        return False

    def remove_occupant(self, drone_id: int, target_region: asr.AirspaceRegion) -> bool:
        region_status = target_region.get_status()
        region_owner = target_region.get_owner()
        if region_owner != drone_id:
            return False
        if region_status is asr.RegionStatus.OCCUPIED:
            target_region.update_owner(None, None)
            target_region.update_status(asr.RegionStatus.FREE)
            target_region.clear_timeout()
            return True
        if region_owner is asr.RegionStatus.RESTRICTED_OCCUPIED:
            target_region.update_owner(None, None)
            target_region.update_status(asr.RegionStatus.RESTRICTED_AVAILABLE)
            target_region.clear_timeout()
            return True
        return False
