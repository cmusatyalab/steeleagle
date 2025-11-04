import time
from enum import Enum
import logging
from typing import Optional

# Set up logger for regions
logger = logging.getLogger("airspace.region")
security_logger = logging.getLogger("airspace.security")


class RegionStatus(Enum):
    FREE = 1
    ALLOCATED = 2
    OCCUPIED = 3
    RESTRICTED_AVAILABLE = 4
    RESTRICTED_ALLOCATED = 5
    RESTRICTED_OCCUPIED = 6
    NOFLY = 7


class AirspaceRegion:
    def __init__(
        self, min_alt: float, max_alt: float, corners: list[tuple[float, float]], c_id: int
    ):
        self.c_id = c_id
        self.min_alt = min_alt
        self.max_alt = max_alt
        self.region_id: str | None = None  # Will be set to geohash by the engine

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
        self.lateral_neighbors: set[str] = set()  # Same altitude neighbors (8)
        self.upper_neighbors: set[str] = set()  # Higher altitude neighbors  (9)
        self.lower_neighbors: set[str] = set()  # Lower altitude neighbors (9)

        logger.info(
            f"c_id: {self.c_id} >> AirspaceRegion created: lat={self.min_lat:.4f}, {self.max_lat:.4f}, "
            f"lon={self.min_lon:.4f}, {self.max_lon:.4f}, alt={self.min_alt:.0f} <-> {self.max_alt:.0f}, "
            f"corners: {self.corners}"
        )

    def contains(self, ref_lat: float, ref_lon: float, ref_alt: float) -> bool:
        CORNER_COUNT = 4
        if ref_alt < self.min_alt or ref_alt > self.max_alt:
            logger.debug(
                f"c_id: {self.c_id} >> Point ({ref_lat:.4f}, {ref_lon:.4f}, {ref_alt:.0f})"
                f" outside altitude bounds of region {self.region_id}"
            )
            return False
        # line-side test lateral point against corners
        for i in range(CORNER_COUNT):
            if ref_lat <= self.max_lat and ref_lat >= self.min_lat:
                if ref_lon <= self.max_lon and ref_lon >= self.min_lon:
                    logger.debug(
                    f"c_id: {self.c_id} >> Point ({ref_lat:.4f}, {ref_lon:.4f}, {ref_alt:.0f})"
                    f" contained in region {self.region_id}"
                    )
                    return True 
            #if not self.line_side_test(
            #    self.corners[i], self.corners[i + 1 % CORNER_COUNT], (ref_lat, ref_lon)
            #):
        logger.debug(
            f"c_id: {self.c_id} >> Point ({ref_lat:.4f}, {ref_lon:.4f}, {ref_alt:.0f})"
            " outside lateral bounds of region {self.region_id}"
            )
        return False

    def set_id(self, id: str):
        self.region_id = id

    def get_centroid(self) -> tuple[float, float, float]:
        # assumes all regions are squares (works regardless of orientation)
        lat_center = (self.min_lat + self.max_lat) / 2
        lon_center = (self.min_lon + self.max_lon) / 2
        alt_center = (self.min_alt + self.max_alt) / 2
        return (lat_center, lon_center, alt_center)

    def get_corners_3d(self) -> list[tuple[float, float, float]]:
        corners_3d = []
        for lat, lon in self.corners:
            corners_3d.extend([(lat, lon, self.min_alt), (lat, lon, self.max_alt)])
        return corners_3d

    def add_lateral_neighbor(self, neighbor_id: str):
        if neighbor_id not in self.lateral_neighbors:
            self.lateral_neighbors.add(neighbor_id)
            #logger.info(
            #    f"c_id: {self.c_id} >> Added lateral neighbor {neighbor_id} to region {self.region_id}"
            #)

    def add_upper_neighbor(self, neighbor_id: str):
        if neighbor_id not in self.upper_neighbors:
            self.upper_neighbors.add(neighbor_id)
            #logger.info(
            #    f"c_id: {self.c_id} >> Added upper neighbor {neighbor_id} to region {self.region_id}"
            #)

    def add_lower_neighbor(self, neighbor_id: str):
        if neighbor_id not in self.lower_neighbors:
            self.lower_neighbors.add(neighbor_id)
            logger.info(
                f"c_id: {self.c_id} >> Added lower neighbor {neighbor_id} to region {self.region_id}"
            )

    def remove_lateral_neighbor(self, neighbor_id: str):
        if neighbor_id in self.lateral_neighbors:
            self.lateral_neighbors.discard(neighbor_id)
            #logger.info(
            #    f"c_id: {self.c_id} >> Removed lateral neighbor {neighbor_id} from region {self.region_id}"
            #)

    def remove_upper_neighbor(self, neighbor_id: str):
        if neighbor_id in self.upper_neighbors:
            self.upper_neighbors.discard(neighbor_id)
            #logger.info(
            #    f"c_id: {self.c_id} >> Removed upper neighbor {neighbor_id} from region {self.region_id}"
            #)

    def remove_lower_neighbor(self, neighbor_id: str):
        if neighbor_id in self.lower_neighbors:
            self.lower_neighbors.discard(neighbor_id)
            #logger.info(
            #    f"c_id: {self.c_id} >> Removed lower neighbor {neighbor_id} from region {self.region_id}"
            #)

    def get_all_neighbor(self) -> set[str]:
        return self.lateral_neighbors | self.upper_neighbors | self.lower_neighbors

    def get_upper_neighbors(self) -> set[str]:
        return self.upper_neighbors
    
    def get_lower_neighbors(self) -> set[str]:
        return self.lower_neighbors
    
    def get_lateral_neighbors(self) -> set[str]:
        return self.lateral_neighbors

    def shares_side_with(self, other: "AirspaceRegion") -> bool:
        if other is None or other.region_id is None:
            return False

        lat_adjacent = (
            abs(self.max_lat - other.min_lat) <= 1e-9
            or abs(self.min_lat - other.max_lat) < 1e-9
        )
        lon_adjacent = (
            abs(self.max_lon - other.min_lon) <= 1e-9
            or abs(self.min_lon - other.max_lon) < 1e-9
        )
        alt_adjacent = (
            abs(self.max_alt - other.min_alt) <= 1e-9
            or abs(self.min_alt - other.max_alt) < 1e-9
        )

        # Check overlap in the other two dimensions
        lat_overlap = not (
            self.max_lat <= other.min_lat or self.min_lat >= other.max_lat
        )
        lon_overlap = not (
            self.max_lon <= other.min_lon or self.min_lon >= other.max_lon
        )
        alt_overlap = not (
            self.max_alt <= other.min_alt or self.min_alt >= other.max_alt
        )

        # Regions share a side if they're adjacent in one dimension and overlap in the other two
        shares_side = (
            (lat_adjacent and lon_overlap and alt_overlap)
            or (lon_adjacent and lat_overlap and alt_overlap)
            or (alt_adjacent and lat_overlap and lon_overlap)
        )

        if shares_side:
            logger.info(f"c_id: {self.c_id} >> Region {self.region_id} shares side with {other.region_id}")

        return shares_side

    def get_altitude_bounds(self) -> tuple[float, float]:
        return (self.min_alt, self.max_alt)

    def get_lat_bounds(self) -> tuple[float, float]:
        return (self.min_lat, self.max_lat)

    def get_lon_bounds(self) -> tuple[float, float]:
        return (self.min_lon, self.max_lon)

    def get_bounds(
        self,
    ) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
        return (
            self.get_lat_bounds(),
            self.get_lon_bounds(),
            self.get_altitude_bounds(),
        )

    def overlaps_with(self, other: "AirspaceRegion") -> bool:
        if other is None:
            return False

        lat_overlap = not (
            self.max_lat <= other.min_lat or self.min_lat >= other.max_lat
        )
        lon_overlap = not (
            self.max_lon <= other.min_lon or self.min_lon >= other.max_lon
        )
        alt_overlap = not (
            self.max_alt <= other.min_alt or self.min_alt >= other.max_alt
        )

        overlaps = lat_overlap and lon_overlap and alt_overlap

        if overlaps:
            logger.warning(f"c_id: {self.c_id} >> Region {self.region_id} overlaps with {other.region_id}")

        return overlaps

    def is_available(self) -> bool:
        available = self.status is RegionStatus.FREE
        logger.info(
            f"c_id: {self.c_id} >> Region {self.region_id} availability check: {available} (status: {self.status.name})"
        )
        return available

    def is_available_priority(self, req_priority: int) -> bool:
        if (
            self.status is RegionStatus.FREE
            or self.status is RegionStatus.RESTRICTED_AVAILABLE
        ):
            logger.info(
                f"c_id: {self.c_id} >> Region {self.region_id} available for priority {req_priority} (status: {self.status.name})"
            )
            return True

        if (
            self.status is RegionStatus.ALLOCATED
            or self.status is RegionStatus.RESTRICTED_ALLOCATED
        ):
            if self.owner_priority is not None:
                can_override = req_priority > self.owner_priority
                logger.info(
                    f"c_id: {self.c_id} >> Region {self.region_id} priority check: req={req_priority} vs current={self.owner_priority}, can_override={can_override}"
                )
                return can_override
            return True

        logger.info(
            f"c_id: {self.c_id} >> Region {self.region_id} not available for priority {req_priority} (status: {self.status.name})"
        )
        return False

    def get_priority(self) -> int | None:
        return self.owner_priority

    def get_owner(self) -> int | None:
        return self.owner

    def get_status(self) -> RegionStatus:
        return self.status

    def update_status(self, new_status: RegionStatus):
        if self.status != new_status:
            old_status = self.status.name
            logger.info(
                f"c_id: {self.c_id} >> Region {self.region_id} status changed: {old_status} -> {new_status.name}"
            )

            # Log critical status changes to security log
            if new_status in [
                RegionStatus.NOFLY,
                RegionStatus.RESTRICTED_AVAILABLE,
                RegionStatus.RESTRICTED_ALLOCATED,
                RegionStatus.RESTRICTED_OCCUPIED,
            ]:
                security_logger.warning(
                    f"c_id: {self.c_id} >> CRITICAL STATUS CHANGE: {self.c_id}; Region {self.region_id} -> {new_status.name}"
                )

        self.status = new_status

    def check_owner(self, drone_id):
        return drone_id == self.get_owner()

    def update_owner(self, new_owner: int | None, new_owner_priority: int | None):
        if self.owner != new_owner:
            old_owner = self.owner
            logger.info(
                f"c_id: {self.c_id} >> Region {self.region_id} owner changed: {old_owner} -> {new_owner} (priority: {new_owner_priority})"
            )

            # Log ownership changes to security log
            if new_owner is not None:
                security_logger.info(
                    f"c_id: {self.c_id} >> OWNERSHIP GRANTED: Region {self.region_id} assigned to drone {new_owner} (priority: {new_owner_priority})"
                )
            else:
                security_logger.info(
                    f"c_id: {self.c_id} >> OWNERSHIP RELEASED: Region {self.region_id} released from drone {old_owner}"
                )

        self.owner = new_owner
        self.owner_priority = new_owner_priority

    def update_priority(self, new_priority: int | None):
        if self.owner_priority != new_priority:
            old_priority = self.owner_priority
            logger.info(
                f"c_id: {self.c_id} >> Region {self.region_id} priority updated: {old_priority} -> {new_priority}"
            )
        self.owner_priority = new_priority

    def update_min_alt(self, new_min_alt: float):
        if self.min_alt != new_min_alt:
            logger.info(
                f"c_id: {self.c_id} >> Region {self.region_id} min_alt updated: {self.min_alt} -> {new_min_alt}"
            )
        self.min_alt = new_min_alt

    def update_max_alt(self, new_max_alt: float):
        if self.max_alt != new_max_alt:
            logger.info(
                f"c_id: {self.c_id} >> Region {self.region_id} max_alt updated: {self.max_alt} -> {new_max_alt}"
            )
        self.max_alt = new_max_alt

    def update_min_lat(self, new_min_lat: float):
        if self.min_lat != new_min_lat:
            logger.info(
                f"c_id: {self.c_id} >> Region {self.region_id} min_lat updated: {self.min_lat} -> {new_min_lat}"
            )
        self.min_lat = new_min_lat

    def update_max_lat(self, new_max_lat: float):
        if self.max_lat != new_max_lat:
            logger.info(
                f"c_id: {self.c_id} >> Region {self.region_id} max_lat updated: {self.max_lat} -> {new_max_lat}"
            )
        self.max_lat = new_max_lat

    def update_min_lon(self, new_min_lon: float):
        if self.min_lon != new_min_lon:
            logger.info(
                f"c_id: {self.c_id} >> Region {self.region_id} min_lon updated: {self.min_lon} -> {new_min_lon}"
            )
        self.min_lon = new_min_lon

    def update_max_lon(self, new_max_lon: float):
        if self.max_lon != new_max_lon:
            logger.info(
                f"c_id: {self.c_id} >> Region {self.region_id} max_lon updated: {self.max_lon} -> {new_max_lon}"
            )
        self.max_lon = new_max_lon

    def update_corners(self, new_corners: list[tuple[float, float]]):
        if self.corners != new_corners:
            logger.info(
                f"c_id: {self.c_id} >> Region {self.region_id} corners updated: {self.corners} -> {new_corners}"
            )
            # Recalculate bounds when corners change
            self.min_lat = new_corners[0][0]
            self.max_lat = new_corners[0][0]
            self.min_lon = new_corners[0][1]
            self.max_lon = new_corners[0][1]
            for c in new_corners[1:]:
                if c[0] < self.min_lat:
                    self.min_lat = c[0]
                elif c[0] > self.max_lat:
                    self.max_lat = c[0]
                if c[1] < self.min_lon:
                    self.min_lon = c[1]
                elif c[1] > self.max_lon:
                    self.max_lon = c[1]

        self.corners = new_corners

    def set_timeout(self, length: float):
        self.timeout_len = length
        self.timeout_ref = time.time()
        logger.info(
            f"c_id: {self.c_id} >> Region {self.region_id} timeout set: {length}s for drone {self.owner}"
        )

    def clear_timeout(self):
        if self.timeout_len is not None:
            logger.info(
                f"c_id: {self.c_id} >> Region {self.region_id} timeout cleared for drone {self.owner}"
            )
        self.timeout_len = None
        self.timeout_ref = None

    def check_timeout(self) -> bool:
        if self.timeout_len is None or self.timeout_ref is None:
            return False

        current_time = time.time()
        expired = current_time >= self.timeout_len + self.timeout_ref

        if expired:
            remaining_time = (self.timeout_len + self.timeout_ref) - current_time
            logger.warning(
                f"c_id: {self.c_id} >> Region {self.region_id} lease EXPIRED for drone {self.owner} (overdue by {-remaining_time:.1f}s)"
            )
            security_logger.warning(
                f"c_id: {self.c_id} >> LEASE EXPIRED: Region {self.region_id} lease expired for drone {self.owner}"
            )
        else:
            remaining_time = (self.timeout_len + self.timeout_ref) - current_time
            logger.info(
                f"c_id: {self.c_id} >> Region {self.region_id} lease check: {remaining_time:.1f}s remaining for drone {self.owner}"
            )

        return expired

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

    # might be useful for logging:
    def __str__(self) -> str:
        """String representation of the region"""
        return (
            f"AirspaceRegion(id:{self.region_id}, c_id:{self.c_id}"
            f"lat:{self.min_lat:.4f}-{self.max_lat:.4f}, "
            f"lon:{self.min_lon:.4f}-{self.max_lon:.4f}, "
            f"alt:{self.min_alt:.0f}-{self.max_alt:.0f}, "
            f"status:{self.status.name}, owner:{self.owner})"
        )

    def __repr__(self) -> str:
        """Detailed representation of the region"""
        return self.__str__()
