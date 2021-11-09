#!/usr/bin/env python3

# Copyright 2021 Carnegie Mellon University
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
 Stubs for Jinja Macros
 These stubs are used to validate the tasks
 specified in the description fields of the KML.
 Each class should contain two attributes that
 are assigned in the __init__ method: a JSON schema
 for validation and a python dict that holds any
 default values
"""
class heimdall_TakePhotosAlongPath:
    def __init__(self):
        self.schema = {
                    "title": "TakePhotosAlongPath",
                    "description": "Instruct drone to take photos at the coordinates specified by the path",
                    "properties": {
                        "mode": {
                        "description": "Photo Mode",
                        "type": "string",
                        "enum": ["SINGLE", "BURST", "TIME", "GPS"]
                        },
                        "interval": {
                        "description": "Interval between photos (in seconds or meters)",
                        "type": "number",
                        "minimum": 1
                        },
                        "gimbal_pitch": {
                        "description": "The angle of the gimbal",
                        "type": "number",
                        "minimum": -90,
                        "maximum": 90,
                        "default": -90
                        },
                        "drone_rotation": {
                        "description": "The heading offset to rotate the drone to ",
                        "type": "number",
                        "minimum": 0,
                        "maximum": 360
                        },
                    },
                    "required": [ "mode" ]
                }
        self.defaults = {'mode': 'SINGLE', 'interval': 5, 'gimbal_pitch': -90.0, 'drone_rotation': 0.0}

class SetNewHome:
    def __init__(self):
        self.schema = {
                    "title": "SetNewHome",
                    "description": "Set the return to home point to the coordinates",
                }
        self.defaults = {}

class MoveTo:
    def __init__(self):
        self.schema = {
                    "title": "MoveTo",
                    "description": "Fly to coordinates specified by placemark",
                }
        self.defaults = {}

class Land:
    def __init__(self):
        self.schema = {
                    "title": "Land",
                    "description": "Instruct the drone to initiate landing at this point",
                }
        self.defaults = {}

class heimdall_DetectObjectsAlongPath:
    def __init__(self):
        self.schema = {
                    "title": "DetectObjectsAlongPath",
                    "description": "Instruct drone to detect objects along the specified path",
                    "properties": {
                        "gimbal_pitch": {
                        "description": "The angle of the gimbal",
                        "type": "number",
                        "minimum": -90,
                        "maximum": 90,
                        "default": -45
                        },
                        "drone_rotation": {
                        "description": "The heading offset to rotate the drone to at each vertex (in degrees) ",
                        "type": "number",
                        "minimum": 0,
                        "maximum": 360
                        },
                        "sample_rate": {
                        "description": "The number of frames to evaluate per second",
                        "type": "number",
                        "minimum": 1,
                        "maximum": 30
                        },
                        "hover_delay": {
                        "description": "The number of seconds to hover at each vertex before moving to the next",
                        "type": "number",
                        "minimum": 1,
                        "maximum": 10
                        },
                    }
                }
        self.defaults = {'gimbal_pitch': -45.0, 'drone_rotation': 0.0, 'sample_rate': 2, 'hover_delay': 4}