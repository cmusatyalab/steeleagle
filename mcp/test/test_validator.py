from steeleagle_mcp.nl2dsl.validator import validate


def test_validator_accepts_mixed_case_identifiers_allowed_by_grammar():
    dsl = """Data:
    RoutePlan PatrolPath(alt = 20.0, area = PatrolZone, algo = edge)
Actions:
    TakeOff TakeOffAction(take_off_altitude = 10.0)
    Patrol PatrolAction(plan = PatrolPath)
    ReturnToHome ReturnHome()
Mission:
    Start TakeOffAction
    During TakeOffAction:
        done -> PatrolAction
    During PatrolAction:
        done -> ReturnHome
"""

    assert validate(dsl) == []
