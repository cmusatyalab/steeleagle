"""Shared fixtures for the translation and route tests. REGISTRY is a
recording of the real `eaglec schema` output for the default imports (see
Task 4 of the 2026-10-14 eaglec plan for how to regenerate it)."""

import json
from pathlib import Path

from app.compiler_config import DEFAULT_IMPORTS, SDK_MODULE
from app.mission_translate import TypeIndex

REGISTRY: dict = json.loads(
    (Path(__file__).parent / "fixtures" / "registry.json").read_text()
)
INDEX = TypeIndex(REGISTRY)

HEADER = {
    "Modules": {"Modules": [{"Path": SDK_MODULE, "Override": "/repo/sdk"}]},
    "Imports": {"Imports": [{"Path": p} for p in DEFAULT_IMPORTS]},
}

GRAPH = {
    "nodes": [
        {"instance_id": "takeoff", "type_name": "TakeOff", "params": {"Altitude": 5}},
        {
            "instance_id": "gimbal",
            "type_name": "SetGimbalPose",
            "params": {
                "Pose": {"Pitch": -30, "Roll": 0, "Yaw": 0},
                "AngleMode": "AngleModeAbsolute",
            },
        },
        {
            "instance_id": "patrol",
            "type_name": "Patrol",
            "params": {"Area": "Poly", "Altitude": 15, "Pattern": "PatrolModeSurvey"},
        },
        {"instance_id": "land", "type_name": "Land", "params": {}},
    ],
    "events": [
        {
            "instance_id": "low",
            "type_name": "Battery",
            "params": {"Comparator": "LessOrEqual", "Threshold": 15},
        }
    ],
    "edges": [
        {"source": "takeoff", "event_id": "done", "target": "gimbal"},
        {"source": "gimbal", "event_id": "done", "target": "patrol"},
        {"source": "patrol", "event_id": "low", "target": "land"},
        {"source": "patrol", "event_id": "done", "target": "land"},
    ],
    "start_id": "takeoff",
}

AST = {
    **HEADER,
    "Actions": {
        "Decls": [
            {
                "Type": "actions.TakeOff",
                "Name": "takeoff",
                "Attrs": [{"Key": "Altitude", "Value": {"Float": 5.0}}],
            },
            {
                "Type": "actions.SetGimbalPose",
                "Name": "gimbal",
                "Attrs": [
                    {
                        "Key": "Pose",
                        "Value": {
                            "Inline": {
                                "Type": "datatypes.Pose",
                                "Args": [
                                    {"Key": "Pitch", "Value": {"Float": -30.0}},
                                    {"Key": "Roll", "Value": {"Float": 0.0}},
                                    {"Key": "Yaw", "Value": {"Float": 0.0}},
                                ],
                            }
                        },
                    },
                    {"Key": "AngleMode", "Value": {"Ident": "enums.AngleModeAbsolute"}},
                ],
            },
            {
                "Type": "actions.Patrol",
                "Name": "patrol",
                "Attrs": [
                    {"Key": "Area", "Value": {"Ident": "params.Polygon_Poly"}},
                    {"Key": "Altitude", "Value": {"Float": 15.0}},
                    {"Key": "Pattern", "Value": {"Ident": "actions.PatrolModeSurvey"}},
                ],
            },
            {"Type": "actions.Land", "Name": "land", "Attrs": []},
        ]
    },
    "Events": {
        "Decls": [
            {
                "Type": "events.Battery",
                "Name": "low",
                "Attrs": [
                    {"Key": "Comparator", "Value": {"Ident": "events.LessOrEqual"}},
                    {"Key": "Threshold", "Value": {"Int": 15}},
                ],
            }
        ]
    },
    "Mission": {
        "Start": "takeoff",
        "Blocks": [
            {"Action": "takeoff", "Rules": [{"Event": "done", "Next": "gimbal"}]},
            {"Action": "gimbal", "Rules": [{"Event": "done", "Next": "patrol"}]},
            {
                "Action": "patrol",
                "Rules": [
                    {"Event": "low", "Next": "land"},
                    {"Event": "done", "Next": "land"},
                ],
            },
        ],
    },
}

POLY_GEOJSON = json.dumps(
    {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "Poly"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [-79.9468, 40.4128],
                            [-79.9463, 40.4133],
                            [-79.9458, 40.4130],
                            [-79.9463, 40.4124],
                            [-79.9468, 40.4128],
                        ]
                    ],
                },
            }
        ],
    }
)


DSL = """Modules:
    "github.com/cmusatyalab/steeleagle/sdk" => "/repo/sdk"

Imports:
    "github.com/cmusatyalab/steeleagle/sdk/dsl/actions"
    "github.com/cmusatyalab/steeleagle/sdk/dsl/events"
    "github.com/cmusatyalab/steeleagle/sdk/dsl/datatypes"
    "github.com/cmusatyalab/steeleagle/sdk/params"
    "github.com/cmusatyalab/steeleagle/sdk/enums"

Actions:
    actions.TakeOff takeoff(Altitude=5.0)
    actions.SetGimbalPose gimbal(Pose=datatypes.Pose(Pitch=-30.0, Roll=0.0, Yaw=0.0), AngleMode=enums.AngleModeAbsolute)
    actions.Patrol patrol(Area=params.Polygon_Poly, Altitude=15.0, Pattern=actions.PatrolModeSurvey)
    actions.Land land()

Events:
    events.Battery low(Comparator=events.LessOrEqual, Threshold=15)

Mission:
    Start takeoff
    During takeoff:
        done -> gimbal
    During gimbal:
        done -> patrol
    During patrol:
        low -> land
        done -> land
"""
