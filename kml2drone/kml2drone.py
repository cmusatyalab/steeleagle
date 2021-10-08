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

import os
import sys
import argparse
import py_compile
import xml.etree.ElementTree as ET
from zipfile import ZipFile
import jinja2
import yaml
import jsonschema

KML_NAMESPACE = '{http://www.opengis.net/kml/2.2}'
HR = '==============={0}===================='
FIXED_ALTITUDE = 6.0 #meters

# Stubs for Jinja Macros
class TakePhotosAlongPath:
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
                        "maximim": 90
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
        self.defaults = {'mode': 'BURST', 'interval': 5, 'gimbal_pitch': -90.0, 'drone_rotation': 0.0}

class SetNewHome:
    def __init__(self):
        self.schema = {
                    "title": "SetNewHome",
                    "description": "Set the return to home point to the coordinates",
                }
        self.defaults = {}

#Representation of a point/line/polygon from MyMaps
class Placemark:

    def __init__(self):
        self.name = ""
        self.description = ""
        self.task = ""
        self.kwargs = {}
        self.coords = []

    def parseCoordinates(self, coords):
        '''
        <coordinates>
            long0,lat0,altitude0
            ...
            longN,latN,altitudeN
        </coordinates>
        '''
        for line in coords.text.strip().split('\n'):
            stripped = line.strip()
            lng,lat,alt = stripped.split(',')
            self.coords.append({'lng': float(lng), 'lat': float(lat), 'alt': FIXED_ALTITUDE if float(alt) < 1 else alt})

    def print(self):
        print(self.name)
        print(self.description)

    def validate(self):
        if self.description == "":
            print("WARNING: {} has no task specification. If it is not referenced by another placemark's task, it will be ignored.".format(self.name))
        else:
            try:
                for k, v in self.description.items():
                    self.task = k
                    self.kwargs = v
                    obj = eval("{}()".format(self.task))
                    self.kwargs['coords'] = self.coords #add the coordinates to the list of args
                    self.kwargs = {**obj.defaults, **self.kwargs}  #merge default args
                    jsonschema.validate(self.kwargs, obj.schema)
            except NameError:
                print(f"ERROR: The task ({self.task}) specified in the description of {self.name} is not found")
                exit(-1)
            except SyntaxError as e:
                print(f"ERROR: Syntax error in the task specification of {self.name} [{e}]")
                exit(-1)
            except Exception as e:
                print(f"ERROR: Unknown error validating task specification for {self.name} [{e}]")
                exit(-1)

def generateOlympeScript(args, placemarks):
    env = jinja2.Environment(loader = jinja2.FileSystemLoader("templates"))
    template = env.get_template(args.template)
    out = template.render(placemarks=placemarks, dashboard_address=args.dashboard_address, dashboard_port=args.dashboard_port)
    return out

def parseKML(args):
    print(HR.format("Parsing KML"))
    tree = ET.parse(args.input)
    root = tree.getroot()
    placemarks = {}
    out = ""
    for placemark in root.iter(KML_NAMESPACE+'Placemark'):
        p = Placemark()
        for child in placemark:
            if child.tag == KML_NAMESPACE+'name':
                p.name = child.text.strip()
                if args.verbose:
                    print(f"Processing {child.text.strip()} placemark...")
            elif child.tag == KML_NAMESPACE+'description':
                p.description = yaml.load(child.text.strip().replace("<br>", "\n"))
            for coord in child.iter(KML_NAMESPACE+'coordinates'):
                p.parseCoordinates(coord)

        placemarks[p.name] = p
    for k,v in placemarks.items():
        v.validate()

    if args.platform == 'anafi':
        out = generateOlympeScript(args, placemarks)
    elif args.platform == 'dji':
        raise Exception(f'Mappings not implemented for {args.platform}.')
    else:
        raise Exception('Unsupported drone platfrom specified')

    return out

def _main():
    parser = argparse.ArgumentParser(prog='kml2drone', 
        description='Convert kml/kmz file to drone-specific instructions.')
    parser.add_argument('input', help='kml/kmz file to convert')
    parser.add_argument('-p', '--platform', choices=['anafi', 'dji'], default='anafi',
        help='Drone platform to convert to  [default: Anafi (Olympe)]')
    parser.add_argument('-o', '--output', default='flightplan.py',
        help='Filename for generated drone instructions [default: flightplan.py]')
    parser.add_argument('-v', '--verbose', action='store_true', 
        help='Write output to console as well [default: False]')
    parser.add_argument('-t', '--template', default='/anafi/base.py.jinja2',
        help='Specify a jinja2 template [default: /anafi/base.py.jinja2]')
    parser.add_argument('-da', '--dashboard_address', default='transponder.pgh.cloudapp.azurelel.cs.cmu.edu',
        help='Specify address of dashboard to send heartbeat to [default: transponder.pgh.cloudapp.azurelel.cs.cmu.edu]')
    parser.add_argument('-dp', '--dashboard_port', default='8080',
        help='Specify dashboard port [default: 8080]')

    if len(sys.argv) == 1:
        parser.print_help()
    args = parser.parse_args()
    if(args.verbose):
        print(HR.format("kml2drone"))
        print(f"Input File:\t\t{args.input}")
        print(f"Drone Platform:\t\t{args.platform}")
        print(f"Output File:\t\t{args.output}")

    _, extension = os.path.splitext(args.input)
    if extension == '.kmz':
        print(HR.format("Extracting KMZ"))
        with ZipFile(args.input) as kmz:
            with kmz.open('doc.kml') as kml:
                args.input = kml
                out = parseKML(args)
    else:
        out = parseKML(args)

    with open(args.output, mode='w', encoding='utf-8') as f:
        f.write(out)

    if args.platform == 'anafi':
        #compile to find syntax errrors in python script
        py_compile.compile(args.output, doraise=True)
        print(HR.format(f"Script {args.output} compiled"))
    if args.verbose:
        print(HR.format(f"Output for {args.platform}"))
        print(out)

if __name__ == "__main__":
    _main()
