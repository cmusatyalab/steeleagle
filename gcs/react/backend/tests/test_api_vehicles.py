import pytest

from app.api import Vehicle, _build_vehicle

GOOD_FIELDS = {
    "model": "parrot_anafi",
    "mag": "0",
    "last_seen": "0",
    "position_info.home_lat": "40.44353",
    "position_info.home_long": "-79.94299",
    "position_info.home_alt": "0.0",
}

GOOD_TELEM_ENTRY = (
    "1-0",
    {
        "latitude": "40.44353",
        "longitude": "-79.94299",
        "rel_altitude": "10.0",
        "bearing": "45.0",
        "battery": "80",
        "sats": "2",
        "v_body_forward": "1.0",
        "v_body_lateral": "0.0",
        "v_body_altitude": "0.0",
        "v_body_angular": "0.0",
    },
)


def test_builds_a_valid_vehicle_from_good_data():
    vehicle = _build_vehicle("alpha-1", GOOD_FIELDS, [GOOD_TELEM_ENTRY])

    assert isinstance(vehicle, Vehicle)
    assert vehicle.name == "alpha-1"
    assert vehicle.battery == 80
    assert vehicle.velocity.x_vel == 1.0


def test_missing_telemetry_raises_key_error_not_crash():
    with pytest.raises(KeyError):
        _build_vehicle("alpha-1", GOOD_FIELDS, [])


def test_missing_redis_field_raises_key_error():
    incomplete_fields = dict(GOOD_FIELDS)
    del incomplete_fields["model"]

    with pytest.raises(KeyError):
        _build_vehicle("alpha-1", incomplete_fields, [GOOD_TELEM_ENTRY])


def test_out_of_range_gps_fix_raises_value_error_not_crash():
    # A vehicle with no GPS fix reporting an out-of-range sentinel like
    # (500, 500) instead of a real lat/long -- must not crash the caller.
    no_fix_telem = (
        "1-0",
        {**GOOD_TELEM_ENTRY[1], "latitude": "500", "longitude": "500"},
    )

    with pytest.raises(ValueError):
        _build_vehicle("alpha-1", GOOD_FIELDS, [no_fix_telem])
