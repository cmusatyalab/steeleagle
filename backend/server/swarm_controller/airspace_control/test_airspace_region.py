import pytest
import time
import airspace_region as asr


class TestRegionInitialization:
    def test_region_created_with_correct_bounds(self):
        corners = [
            (40.0, -74.0),
            (39.9, -74.0),
            (39.9, -73.9),
            (40.0, -73.9),
        ]
        region = asr.AirspaceRegion(0.0, 100.0, corners, c_id=1)
        
        assert region.min_lat == 39.9
        assert region.max_lat == 40.0
        assert region.min_lon == -74.0
        assert region.max_lon == -73.9
        assert region.min_alt == 0.0
        assert region.max_alt == 100.0

    def test_region_starts_with_free_status(self):
        corners = [(40.0, -74.0), (39.9, -74.0), (39.9, -73.9), (40.0, -73.9)]
        region = asr.AirspaceRegion(0.0, 100.0, corners, c_id=1)
        
        assert region.status == asr.RegionStatus.FREE
        assert region.owner is None
        assert region.owner_priority is None


class TestContainment:
    def test_contains_point_inside_region(self):
        corners = [(40.0, -74.0), (39.9, -74.0), (39.9, -73.9), (40.0, -73.9)]
        region = asr.AirspaceRegion(0.0, 100.0, corners, c_id=1)
        
        assert region.contains(39.95, -73.95, 50.0) is True

    def test_rejects_point_outside_latitude(self):
        corners = [(40.0, -74.0), (39.9, -74.0), (39.9, -73.9), (40.0, -73.9)]
        region = asr.AirspaceRegion(0.0, 100.0, corners, c_id=1)
        
        assert region.contains(40.1, -73.95, 50.0) is False

    def test_rejects_point_outside_altitude(self):
        corners = [(40.0, -74.0), (39.9, -74.0), (39.9, -73.9), (40.0, -73.9)]
        region = asr.AirspaceRegion(0.0, 100.0, corners, c_id=1)
        
        assert region.contains(39.95, -73.95, 150.0) is False


class TestGeometry:
    def test_get_centroid(self):
        corners = [(40.0, -74.0), (39.9, -74.0), (39.9, -73.9), (40.0, -73.9)]
        region = asr.AirspaceRegion(0.0, 100.0, corners, c_id=1)
        
        lat, lon, alt = region.get_centroid()
        assert lat == pytest.approx(39.95)
        assert lon == pytest.approx(-73.95)
        assert alt == pytest.approx(50.0)

    def test_get_corners_3d(self):
        corners = [(40.0, -74.0), (39.9, -74.0), (39.9, -73.9), (40.0, -73.9)]
        region = asr.AirspaceRegion(0.0, 100.0, corners, c_id=1)
        
        corners_3d = region.get_corners_3d()
        assert len(corners_3d) == 8
        
        altitudes = {c[2] for c in corners_3d}
        assert altitudes == {0.0, 100.0}


class TestNeighborManagement:
    def test_add_lateral_neighbor(self):
        corners = [(40.0, -74.0), (39.9, -74.0), (39.9, -73.9), (40.0, -73.9)]
        region = asr.AirspaceRegion(0.0, 100.0, corners, c_id=1)
        
        region.add_lateral_neighbor("neighbor1")
        assert "neighbor1" in region.lateral_neighbors

    def test_add_duplicate_neighbor_ignored(self):
        corners = [(40.0, -74.0), (39.9, -74.0), (39.9, -73.9), (40.0, -73.9)]
        region = asr.AirspaceRegion(0.0, 100.0, corners, c_id=1)
        
        region.add_lateral_neighbor("neighbor1")
        region.add_lateral_neighbor("neighbor1")
        assert len(region.lateral_neighbors) == 1

    def test_remove_lateral_neighbor(self):
        corners = [(40.0, -74.0), (39.9, -74.0), (39.9, -73.9), (40.0, -73.9)]
        region = asr.AirspaceRegion(0.0, 100.0, corners, c_id=1)
        
        region.add_lateral_neighbor("neighbor1")
        region.remove_lateral_neighbor("neighbor1")
        assert "neighbor1" not in region.lateral_neighbors

    def test_get_all_neighbors(self):
        corners = [(40.0, -74.0), (39.9, -74.0), (39.9, -73.9), (40.0, -73.9)]
        region = asr.AirspaceRegion(0.0, 100.0, corners, c_id=1)
        
        region.add_lateral_neighbor("lat1")
        region.add_upper_neighbor("up1")
        region.add_lower_neighbor("low1")
        
        all_neighbors = region.get_all_neighbor()
        assert len(all_neighbors) == 3


class TestAvailability:
    def test_is_available_when_free(self):
        corners = [(40.0, -74.0), (39.9, -74.0), (39.9, -73.9), (40.0, -73.9)]
        region = asr.AirspaceRegion(0.0, 100.0, corners, c_id=1)
        
        assert region.is_available() is True

    def test_not_available_when_allocated(self):
        corners = [(40.0, -74.0), (39.9, -74.0), (39.9, -73.9), (40.0, -73.9)]
        region = asr.AirspaceRegion(0.0, 100.0, corners, c_id=1)
        region.update_status(asr.RegionStatus.ALLOCATED)
        
        assert region.is_available() is False

    def test_is_available_priority_higher_can_override(self):
        corners = [(40.0, -74.0), (39.9, -74.0), (39.9, -73.9), (40.0, -73.9)]
        region = asr.AirspaceRegion(0.0, 100.0, corners, c_id=1)
        region.update_status(asr.RegionStatus.ALLOCATED)
        region.update_owner(100, 3)
        
        assert region.is_available_priority(5) is True

    def test_is_available_priority_lower_cannot_override(self):
        corners = [(40.0, -74.0), (39.9, -74.0), (39.9, -73.9), (40.0, -73.9)]
        region = asr.AirspaceRegion(0.0, 100.0, corners, c_id=1)
        region.update_status(asr.RegionStatus.ALLOCATED)
        region.update_owner(100, 7)
        
        assert region.is_available_priority(5) is False


class TestStatusAndOwnership:
    def test_update_status(self):
        corners = [(40.0, -74.0), (39.9, -74.0), (39.9, -73.9), (40.0, -73.9)]
        region = asr.AirspaceRegion(0.0, 100.0, corners, c_id=1)
        
        region.update_status(asr.RegionStatus.ALLOCATED)
        assert region.get_status() == asr.RegionStatus.ALLOCATED

    def test_update_owner(self):
        corners = [(40.0, -74.0), (39.9, -74.0), (39.9, -73.9), (40.0, -73.9)]
        region = asr.AirspaceRegion(0.0, 100.0, corners, c_id=1)
        
        region.update_owner(123, 5)
        assert region.get_owner() == 123
        assert region.get_priority() == 5

    def test_clear_owner(self):
        corners = [(40.0, -74.0), (39.9, -74.0), (39.9, -73.9), (40.0, -73.9)]
        region = asr.AirspaceRegion(0.0, 100.0, corners, c_id=1)
        
        region.update_owner(123, 5)
        region.update_owner(None, None)
        assert region.get_owner() is None


class TestTimeout:
    def test_set_and_check_timeout_not_expired(self):
        corners = [(40.0, -74.0), (39.9, -74.0), (39.9, -73.9), (40.0, -73.9)]
        region = asr.AirspaceRegion(0.0, 100.0, corners, c_id=1)
        
        region.set_timeout(10.0)
        assert region.check_timeout() is False

    def test_check_timeout_expired(self):
        corners = [(40.0, -74.0), (39.9, -74.0), (39.9, -73.9), (40.0, -73.9)]
        region = asr.AirspaceRegion(0.0, 100.0, corners, c_id=1)
        
        region.set_timeout(0.1)
        time.sleep(0.15)
        assert region.check_timeout() is True

    def test_clear_timeout(self):
        corners = [(40.0, -74.0), (39.9, -74.0), (39.9, -73.9), (40.0, -73.9)]
        region = asr.AirspaceRegion(0.0, 100.0, corners, c_id=1)
        
        region.set_timeout(10.0)
        region.clear_timeout()
        assert region.timeout_len is None