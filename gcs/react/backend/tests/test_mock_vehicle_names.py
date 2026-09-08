from scripts.mock_vehicles import generate_names


def test_returns_requested_count():
    assert len(generate_names("mock-", 5)) == 5


def test_names_are_prefixed():
    names = generate_names("mock-", 5)
    assert all(name.startswith("mock-") for name in names)


def test_names_look_like_color_bird_combos():
    names = generate_names("mock-", 5)
    for name in names:
        # e.g. "mock-silver-falcon" -- prefix, then exactly two more
        # hyphen-separated words (an adjective and a noun).
        suffix = name[len("mock-") :]
        assert len(suffix.split("-")) == 2


def test_names_are_unique_within_a_batch():
    names = generate_names("mock-", 20)
    assert len(set(names)) == len(names)


def test_empty_prefix_is_allowed():
    names = generate_names("", 3)
    assert len(names) == 3
    assert all(name for name in names)
