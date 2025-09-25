import airspace_region as asr

BASE_TIMEOUT = 10  # in seconds


class AirspaceControlEngine:
    def __init__(self, region_corners):
        self.drone_region_map = {}  # drone_id -> region
        self.drone_priority_map = {}  # drone_id -> priority
        self.create_airspace(region_corners)

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
        lat_regions = []
        lon_regions = []
        alt_regions = self.split_by_altitude(base_region, alt_partitions)
        for r in alt_regions:
            lon_regions.extend(self.split_by_longitude(r, lon_partitions))
            # add to self.lon_partitions?
        for r in lon_regions:
            lat_regions.extend(self.split_by_latitude(r, lat_partitions))

    def split_by_latitude(
        self, target_region: asr.AirspaceRegion, num_segments: int
    ) -> list[asr.AirspaceRegion]:
        pass

    def split_by_longitude(
        self, target_region: asr.AirspaceRegion, num_segments: int
    ) -> list[asr.AirspaceRegion]:
        pass

    def split_by_altitude(
        self, target_region: asr.AirspaceRegion, num_segments: int
    ) -> list[asr.AirspaceRegion]:
        pass

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
