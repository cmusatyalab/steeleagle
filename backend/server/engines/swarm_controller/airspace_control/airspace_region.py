import time
from enum import Enum


class RegionStatus(Enum):
    FREE = 1
    ALLOCATED = 2
    OCCUPIED = 3
    RESTRICTED_AVAILABLE = 3
    RESTRICTED_ALLOCATED = 4
    RESTRICTED_OCCUPIED = 5
    NOFLY = 6


class AirspaceRegion:
    def __init__(
        self, min_alt: float, max_alt: float, corners: list[tuple[float, float]]
    ):
        self.min_alt = min_alt
        self.max_alt = max_alt
        self.region_id: str | None = None # Will be set to geohash by the engine

        self.min_lat = corners[0][0]
        self.max_lat = corners[0][0]
        self.min_lon = corners[0][1]
        self.max_lon = corners[0][1]
        for c in corners[1:]:
            if c[0] < self.min_lat:
                self.min_lat = c[0]
            elif c[0] > self.max_lat:
                self.max_lat = c[0]
            if c[1] < self.min_lon:
                self.min_lon = c[1]
            elif c[1] > self.max_lon:
                self.max_lon = c[1]

        self.corners = corners
        self.owner: int | None = None
        self.owner_priority: int | None = None
        self.status = RegionStatus.FREE
        self.timeout_len: float | None = None
        self.timeout_ref: float | None = None

        # Neighbor maps for regions that share sides
        self.lateral_neighbors: set[str] = set()  # Same altitude neighbors (4)
        self.vertical_neighbors: set[str] = set()    # Higher altitude neighbors  (4)
        self.lower_neighbors: set[str] = set()    # Lower altitude neighbors (4)

    def contains(self, ref_lat: float, ref_lon: float, ref_alt: float) -> bool:
        CORNER_COUNT = 4
        if ref_alt < self.min_alt or ref_alt > self.max_alt:
            return False
        # line-side test lateral point against corners
        for i in range(CORNER_COUNT):
            if not self.line_side_test(
                self.corners[i], self.corners[i + 1 % CORNER_COUNT], (ref_lat, ref_lon)
            ):
                return False
        return True
    
    def set_id(self, id: str):
        self.region_id = id
    
    def get_centroid(self) -> tuple[float, float, float]:
        #assumes all regions are squares (works regardless of orientation)
        lat_center = (self.min_lat + self.max_lat) / 2
        lon_center = (self.min_lon + self.max_lon) / 2
        alt_center = (self.min_alt + self.max_alt) / 2
        return (lat_center, lon_center, alt_center)
    
    def get_corners_3d(self) -> list[tuple[float, float, float]]:
        corners_3d = []
        for lat, lon in self.corners:
            corners_3d.extend([
                (lat, lon, self.min_alt),
                (lat, lon, self.max_alt)
            ])
        return corners_3d
    
    def add_lateral_neighbor(self, neighbor_id: str):
        self.lateral_neighbors.add(neighbor_id)
    
    def add_upper_neighbor(self, neighbor_id: str):
        self.upper_neighbors.add(neighbor_id)
    
    def add_lower_neighbor(self, neighbor_id: str):
        self.lower_neighbors.add(neighbor_id)
    
    def reomve_lateral_neighbor(self, neighbor_id: str):
        self.lateral_neighbors.discard(neighbor_id)
    
    def reomve_upper_neighbor(self, neighbor_id: str):
        self.upper_neighbors.discard(neighbor_id)
    
    def reomve_lower_neighbor(self, neighbor_id: str):
        self.lower_neighbors.discard(neighbor_id)

    def get_all_neighbor(self) -> set[str]:
        return self.lateral_neighbors|self.upper_neighbors|self.lower_neighbors
    
    def shares_side_with(self, other: 'AirspaceRegion') -> bool:
        if other is None or other.region_id is None:
            return False

        lat_adjacent = (abs(self.max_lat - other.min_alt) <= 1e-9 
                        or abs(self.min_lat - other.max_alt) < 1e-9)
        lon_adjacent = (abs(self.max_lon - other.min_lon) <= 1e-9 
                        or abs(self.min_lon - other.max_lon) < 1e-9)
        alt_adjacent = (abs(self.max_alt - other.min_alt) <= 1e-9 
                        or abs(self.min_alt - other.max_alt) < 1e-9)
        
        # Check overlap in the other two dimensions
        lat_overlap = not (self.max_lat <= other.min_lat or self.min_lat >= other.max_lat)
        lon_overlap = not (self.max_lon <= other.min_lon or self.min_lon >= other.max_lon)
        alt_overlap = not (self.max_alt <= other.min_alt or self.min_alt >= other.max_alt)
        
        # Regions share a side if they're adjacent in one dimension and overlap in the other two
        return ((lat_adjacent and lon_overlap and alt_overlap) or
                (lon_adjacent and lat_overlap and alt_overlap) or
                (alt_adjacent and lat_overlap and lon_overlap))

    def get_altitude_bounds(self) -> tuple[float, float]:
        pass

    def get_lat_bounds(self)-> tuple[float, float]: 
        pass

    def get_lon_bounds(self)-> tuple[float, float]: 
        pass
    
    def get_bounds(self)-> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
        pass
    
    def overlaps_with(self, other: 'AirspaceRegion')-> bool:
        pass

    def get_volume(self) -> float:
        pass

    def is_available(self) -> bool:
        return self.status is RegionStatus.FREE

    def is_available_priority(self, req_priority: int) -> bool:
        if (
            self.status is RegionStatus.FREE
            or self.status is RegionStatus.RESTRICTED_AVAILABLE
        ):
            return True

        if (
            self.status is RegionStatus.ALLOCATED
            or self.status is RegionStatus.RESTRICTED_ALLOCATED
        ):
            if self.owner_priority is not None:
                return req_priority > self.owner_priority
            return True
        return False

    def get_priority(self) -> int | None:
        return self.owner_priority

    def get_owner(self) -> int | None:
        return self.owner

    def get_status(self) -> RegionStatus:
        return self.status

    def update_status(self, new_status: RegionStatus):
        self.status = new_status

    def update_owner(self, new_owner: int | None, new_owner_priority: int | None):
        self.owner = new_owner
        self.owner_priority = new_owner_priority

    def update_priority(self, new_priority: int | None):
        self.owner_priority = new_priority

    def update_min_alt(self, new_min_alt: float):
        self.min_alt = new_min_alt

    def update_max_alt(self, new_max_alt: float):
        self.max_alt = new_max_alt

    def update_min_lat(self, new_min_lat: float):
        self.min_lat = new_min_lat

    def update_max_lat(self, new_max_lat: float):
        self.max_lat = new_max_lat

    def update_min_lon(self, new_min_lon: float):
        self.min_lon = new_min_lon

    def update_max_lon(self, new_max_lon: float):
        self.max_lat = new_max_lon

    def update_corners(self, new_corners: list[tuple[float, float]]):
        self.corners = new_corners

    def set_timeout(self, length: float):
        self.timeout_len = length
        self.timeout_ref = time.time()

    def clear_timeout(self):
        self.timeout_len = None
        self.timeout_ref = None

    def check_timeout(self) -> bool:
        if self.timeout_len is None or self.timeout_ref is None:
            return False
        else:
            return time.time() >= self.timeout_len + self.timeout_ref

    def cross(
        self,
        base_corner: tuple[float, float],
        end_corner: tuple[float, float],
        ref_point: tuple[float, float],
    ) -> float:
        return ((ref_point[1] - base_corner[1]) * (end_corner[0] - base_corner[0])) - (
            (ref_point[0] - base_corner[0]) * (end_corner[1] - base_corner[1])
        )

    def line_side_test(
        self,
        base_corner: tuple[float, float],
        end_corner: tuple[float, float],
        ref_point: tuple[float, float],
    ):
        cross_prod = self.cross(base_corner, end_corner, ref_point)
        # Convention: False if ref point is right of the line segment, true if on or to the left
        if cross_prod < 0:
            return False
        else:
            return True
        
#might be useful for logging:
    def __str__(self) -> str:
        """String representation of the region"""
        return (f"AirspaceRegion(id:{self.region_id}, "
                f"lat:{self.min_lat:.4f}-{self.max_lat:.4f}, "
                f"lon:{self.min_lon:.4f}-{self.max_lon:.4f}, "
                f"alt:{self.min_alt:.0f}-{self.max_alt:.0f}, "
                f"status:{self.status.name}, owner:{self.owner})")

    def __repr__(self) -> str:
        """Detailed representation of the region"""
        return self.__str__()
