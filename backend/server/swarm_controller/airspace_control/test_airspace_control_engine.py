import pytest
import airspace_control_engine as ace
import airspace_region as asr


class TestEngineInitialization:
    def test_engine_creates_correct_number_of_regions(self):
        corners = [(40.0, -74.0), (39.0, -74.0), (39.0, -73.0), (40.0, -73.0)]
        engine = ace.AirspaceControlEngine(
            region_corners=corners,
            lat_partitions=2,
            lon_partitions=2,
            alt_partitions=2,
            min_alt=0.0,
            max_alt=200.0
        )
        
        assert len(engine.region_map) == 8  # 2×2×2

    def test_single_partition_creates_one_region(self):
        corners = [(40.0, -74.0), (39.0, -74.0), (39.0, -73.0), (40.0, -73.0)]
        engine = ace.AirspaceControlEngine(
            region_corners=corners,
            lat_partitions=1,
            lon_partitions=1,
            alt_partitions=1,
            min_alt=0.0,
            max_alt=100.0
        )
        
        assert len(engine.region_map) == 1


class TestGeohashOperations:
    def test_create_and_parse_geohash_key(self):
        corners = [(40.0, -74.0), (39.0, -74.0), (39.0, -73.0), (40.0, -73.0)]
        engine = ace.AirspaceControlEngine(
            region_corners=corners,
            lat_partitions=2,
            lon_partitions=2,
            alt_partitions=2,
            min_alt=0.0,
            max_alt=200.0
        )
        
        key = engine.create_geohash_key(40.0, -74.0, 50.0)
        base_geohash, alt_discrete = engine.parse_geohash_key(key)
        
        assert isinstance(base_geohash, str)
        assert isinstance(alt_discrete, int)
        assert "_" in key

    def test_get_geohash_neighbors_returns_list(self):
        corners = [(40.0, -74.0), (39.0, -74.0), (39.0, -73.0), (40.0, -73.0)]
        engine = ace.AirspaceControlEngine(
            region_corners=corners,
            lat_partitions=2,
            lon_partitions=2,
            alt_partitions=2,
            min_alt=0.0,
            max_alt=200.0
        )
        
        key = engine.create_geohash_key(40.0, -74.0, 50.0)
        neighbors = engine._get_geohash_neighbors(key, search_radius=1)
        
        assert isinstance(neighbors, list)
        assert len(neighbors) > 0


class TestRegionLookup:
    def test_get_region_from_point_finds_region(self):
        corners = [(40.0, -74.0), (39.0, -74.0), (39.0, -73.0), (40.0, -73.0)]
        engine = ace.AirspaceControlEngine(
            region_corners=corners,
            lat_partitions=2,
            lon_partitions=2,
            alt_partitions=2,
            min_alt=0.0,
            max_alt=200.0
        )
        
        region = engine.get_region_from_point(39.5, -73.5, 50.0)
        assert region is not None

    def test_get_region_from_point_returns_none_for_out_of_bounds(self):
        corners = [(40.0, -74.0), (39.0, -74.0), (39.0, -73.0), (40.0, -73.0)]
        engine = ace.AirspaceControlEngine(
            region_corners=corners,
            lat_partitions=2,
            lon_partitions=2,
            alt_partitions=2,
            min_alt=0.0,
            max_alt=200.0
        )
        
        region = engine.get_region_from_point(50.0, -80.0, 50.0)
        assert region is None

    def test_get_region_from_id(self):
        corners = [(40.0, -74.0), (39.0, -74.0), (39.0, -73.0), (40.0, -73.0)]
        engine = ace.AirspaceControlEngine(
            region_corners=corners,
            lat_partitions=2,
            lon_partitions=2,
            alt_partitions=2,
            min_alt=0.0,
            max_alt=200.0
        )
        
        region_id = next(iter(engine.region_map.keys()))
        region = engine.get_region_from_id(region_id)
        
        assert region is not None
        assert region.region_id == region_id


class TestReservationSystem:
    def test_reserve_free_region(self):
        corners = [(40.0, -74.0), (39.0, -74.0), (39.0, -73.0), (40.0, -73.0)]
        engine = ace.AirspaceControlEngine(
            region_corners=corners,
            lat_partitions=2,
            lon_partitions=2,
            alt_partitions=2,
            min_alt=0.0,
            max_alt=200.0
        )
        
        region = next(iter(engine.region_map.values()))
        engine.set_priority(drone_id=100, new_priority=5)
        
        success = engine.reserve_region(drone_id=100, target_region=region)
        
        assert success is True
        assert region.get_owner() == 100

    def test_reserve_region_owned_by_other_fails(self):
        corners = [(40.0, -74.0), (39.0, -74.0), (39.0, -73.0), (40.0, -73.0)]
        engine = ace.AirspaceControlEngine(
            region_corners=corners,
            lat_partitions=2,
            lon_partitions=2,
            alt_partitions=2,
            min_alt=0.0,
            max_alt=200.0
        )
        
        region = next(iter(engine.region_map.values()))
        engine.set_priority(drone_id=100, new_priority=5)
        engine.set_priority(drone_id=200, new_priority=3)
        
        engine.reserve_region(drone_id=100, target_region=region)
        success = engine.reserve_region(drone_id=200, target_region=region)
        
        assert success is False
        assert region.get_owner() == 100

    def test_renew_region_by_owner(self):
        corners = [(40.0, -74.0), (39.0, -74.0), (39.0, -73.0), (40.0, -73.0)]
        engine = ace.AirspaceControlEngine(
            region_corners=corners,
            lat_partitions=2,
            lon_partitions=2,
            alt_partitions=2,
            min_alt=0.0,
            max_alt=200.0
        )
        
        region = next(iter(engine.region_map.values()))
        engine.set_priority(drone_id=100, new_priority=5)
        engine.reserve_region(drone_id=100, target_region=region)
        
        success = engine.renew_region(drone_id=100, target_region=region)
        assert success is True


class TestOccupancy:
    def test_add_occupant_to_allocated_region(self):
        corners = [(40.0, -74.0), (39.0, -74.0), (39.0, -73.0), (40.0, -73.0)]
        engine = ace.AirspaceControlEngine(
            region_corners=corners,
            lat_partitions=2,
            lon_partitions=2,
            alt_partitions=2,
            min_alt=0.0,
            max_alt=200.0
        )
        
        region = next(iter(engine.region_map.values()))
        engine.set_priority(drone_id=100, new_priority=5)
        engine.reserve_region(drone_id=100, target_region=region)
        
        success = engine.add_occupant(drone_id=100, target_region=region)
        
        assert success is True
        assert region.get_status() == asr.RegionStatus.OCCUPIED

    def test_add_occupant_fails_for_non_owner(self):
        corners = [(40.0, -74.0), (39.0, -74.0), (39.0, -73.0), (40.0, -73.0)]
        engine = ace.AirspaceControlEngine(
            region_corners=corners,
            lat_partitions=2,
            lon_partitions=2,
            alt_partitions=2,
            min_alt=0.0,
            max_alt=200.0
        )
        
        region = next(iter(engine.region_map.values()))
        engine.set_priority(drone_id=100, new_priority=5)
        engine.reserve_region(drone_id=100, target_region=region)
        
        success = engine.add_occupant(drone_id=200, target_region=region)
        
        assert success is False

    def test_remove_occupant(self):
        corners = [(40.0, -74.0), (39.0, -74.0), (39.0, -73.0), (40.0, -73.0)]
        engine = ace.AirspaceControlEngine(
            region_corners=corners,
            lat_partitions=2,
            lon_partitions=2,
            alt_partitions=2,
            min_alt=0.0,
            max_alt=200.0
        )
        
        region = next(iter(engine.region_map.values()))
        engine.set_priority(drone_id=100, new_priority=5)
        engine.reserve_region(drone_id=100, target_region=region)
        engine.add_occupant(drone_id=100, target_region=region)
        
        success = engine.remove_occupant(drone_id=100, target_region=region)
        
        assert success is True
        assert region.get_status() == asr.RegionStatus.FREE
        assert region.get_owner() is None


class TestIntegration:
    def test_complete_drone_lifecycle(self):
        """Test: register -> reserve -> occupy -> exit"""
        corners = [(40.0, -74.0), (39.0, -74.0), (39.0, -73.0), (40.0, -73.0)]
        engine = ace.AirspaceControlEngine(
            region_corners=corners,
            lat_partitions=2,
            lon_partitions=2,
            alt_partitions=2,
            min_alt=0.0,
            max_alt=200.0
        )
        
        region = next(iter(engine.region_map.values()))
        drone_id = 100
        
        engine.set_priority(drone_id, 5)
        assert engine.reserve_region(drone_id, region) is True
        assert engine.add_occupant(drone_id, region) is True
        assert engine.remove_occupant(drone_id, region) is True
        assert region.get_status() == asr.RegionStatus.FREE