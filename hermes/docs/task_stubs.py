#!/usr/bin/env python3

# Copyright 2021 Carnegie Mellon University
# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import sys
import os
import json
import json_schema_for_humans.generate as jsfh

"""
 Stubs for Tasks
 These stubs are used to validate the tasks
 specified in the description fields of the KML.
 Each class should contain two attributes that
 are assigned in the __init__ method: a JSON schema
 for validation and a python dict that holds any
 default values

 Use "additionalProperties": False in the schema
 to disallow additional properties (strict adherence)
"""
class TrackingTask:
     def __init__(self):
        self.schema = {
                    "title": "TrackingTask",
                    "description": "Track specified class using a paritcular model for inteferencing",
                    "examples": ["TrackingTask: {model: 'coco', class: 'person', gimbal_pitch: -30}"],
                    "properties": {
                        "gimbal_pitch": {
                        "description": "The angle of the gimbal",
                        "type": "number",
                        "minimum": -90.0,
                        "maximum": 90.0,
                        "default": -30.0
                        },
                        "model": {
                        "description": "Name of the object detection model to evaluate frames against (default = 'coco')",
                        "type": "string",
                        "enum": ["coco", "robomaster"],
                        "default": "coco"
                        },
                        "class": {
                        "description": "Name of the class to track (default = 'person')",
                        "type": "string",
                        "default": "person"
                        },
                    },
                    "additionalProperties": False
                }
        self.defaults = {'gimbal_pitch': -30.0, 'drone_rotation': 0.0, 'hover_delay': 5, 'model': 'coco', 'class': 'person'}
class TakePhotosAlongPath:
    def __init__(self):
        self.schema = {
                    "title": "TakePhotosAlongPath",
                    "description": "Instruct drone to take photos at the coordinates specified by the path",
                    "examples": ["TakePhotosAlongPath: {mode: 'SINGLE', interval: 10, gimbal_pitch: -45.0}"],
                    "properties": {
                        "mode": {
                        "description": "Photo Mode",
                        "type": "string",
                        "enum": ["SINGLE", "BURST", "TIME", "GPS"],
                        "default": "SINGLE"
                        },
                        "interval": {
                        "description": "Interval between photos (in seconds or meters)",
                        "type": "number",
                        "minimum": 1,
                        "default": 5
                        },
                        "gimbal_pitch": {
                        "description": "The angle of the gimbal",
                        "type": "number",
                        "minimum": -90.0,
                        "maximum": 90.0,
                        "default": -90.0
                        },
                        "drone_rotation": {
                        "description": "The heading offset to rotate the drone to ",
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 360.0,
                        "default": 0.0
                        },
                    },
                    "required": [ "mode" ]
                }
        self.defaults = {'mode': 'SINGLE', 'interval': 5, 'gimbal_pitch': -90.0, 'drone_rotation': 0.0}

class SimpleTask:
    def __init__(self):
        self.schema = {
                    "title": "SimpleTask",
                    "description": "Takeoff, then move",
                    "examples": ["SimpleTask: {}"]
                }
        self.defaults = {}

class SetHome:
    def __init__(self):
        self.schema = {
                    "title": "SetHome",
                    "description": "<span class='badge badge-danger'>Deprecated</span> Set the return to home point to the coordinates",
                    "examples": ["SetHome: {}"]
                }
        self.defaults = {}

class MoveTo:
    def __init__(self):
        self.schema = {
                    "title": "MoveTo",
                    "description": "Fly to coordinates specified by placemark",
                    "examples": ["MoveTo: {}"]
                }
        self.defaults = {}

class ObstacleTask:
    def __init__(self):
        self.schema = {
                    "title": "ObstacleTask",
                    "description": "Fly from coordinate A to coordinate B while avoiding obstacles",
                    "examples": ["ObstacleMoveTo: {model: 'DPT_Large', altitude: 10.0}"],
                    "properties": {
                        "model": {
                        "description": "Model to use for obstacle avoidance",
                        "type": "string",
                        "default": "DPT_Large"
                        },
                        "speed": {
                        "description": "Speed to execute avoidance at",
                        "type": "number",
                        "default": 10
                        },
                        "altitude": {
                        "description": "The altitude (above sea level) to fly at",
                        "type": "number",
                        "default": None
                        }
                    }
                }
        self.defaults = {"model": "DPT_Large", "speed": 10}


class Land:
    def __init__(self):
        self.schema = {
                    "title": "Land",
                    "description": "Instruct the drone to initiate landing at this point",
                    "examples": ["Land: {}"]
                }
        self.defaults = {}

class DetectTask:
     def __init__(self):
        self.schema = {
                    "title": "DetectTask",
                    "description": "Instruct drone to detect objects along the specified path using the specified pitch, rotation, sampling rate, and detection  model",
                    "examples": ["DetectTask: {model: 'coco', sample_rate: 3, hover_delay: 10}"],
                    "properties": {
                        "gimbal_pitch": {
                        "description": "The angle of the gimbal",
                        "type": "number",
                        "minimum": -90.0,
                        "maximum": 90.0,
                        "default": -45.0
                        },
                        "drone_rotation": {
                        "description": "The heading offset to rotate the drone to at each vertex (in degrees) ",
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 360.0,
                        "default": 0.0
                        },
                        "sample_rate": {
                        "description": "The number of frames to evaluate (via OpenScout client) per second",
                        "type": "number",
                        "minimum": 1,
                        "maximum": 30,
                        "default": 2
                        },
                        "hover_delay": {
                        "description": "The number of seconds to hover at each vertex before moving to the next",
                        "type": "number",
                        "minimum": 0,
                        "maximum": 10,
                        "default": 0
                        },
                        "model": {
                        "description": "Name of the object detection model to evaluate frames against (default = 'coco')",
                        "type": "string",
                        "enum": ["coco", "oidv4"],
                        "default": "coco"
                        },
                    },
                    "additionalProperties": False
                }
        self.defaults = {'gimbal_pitch': -45.0, 'drone_rotation': 0.0, 'sample_rate': 2, 'hover_delay': 0, 'model': 'coco'}

def _main():
    #get all class stubs in this module into a dict
    current_module = sys.modules[__name__]
    a = dict([(name, cls) for name, cls in current_module.__dict__.items() if isinstance(cls, type)])

    for k,v in a.items():
        #create an instance of each class
        obj = eval("{}()".format(k))
        #save schema to file
        with open(f'./task_docs/{k}.schema', 'w+') as outfile:
            json.dump(obj.schema, outfile)
        #generate doc
        from json_schema_for_humans.generation_configuration import GenerationConfiguration
        config = GenerationConfiguration(expand_buttons=True, default_from_description=False, footer_show_time=False, description_is_markdown=True)
        jsfh.generate_from_filename(f'./task_docs/{k}.schema', f'./task_docs/{k}.html', config=config)
        #clean up .schema files
        os.remove(f'./task_docs/{k}.schema')

if __name__ == "__main__":
    _main()
