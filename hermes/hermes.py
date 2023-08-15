#!/usr/bin/env python3

# Copyright 2021-2022 Carnegie Mellon University
# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import os
import sys
import argparse
import py_compile
import xml.etree.ElementTree as ET
from zipfile import ZipFile
import jinja2
import yaml
import jsonschema
import docs.task_stubs as task_stubs
import requests
import json
import subprocess

KML_NAMESPACE = '{http://www.opengis.net/kml/2.2}'
HR = '==============={0}===================='
FIXED_ALTITUDE = 15.0 #meters
start = None #starting position, to be assigned

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
                    obj = eval("task_stubs.{}()".format(self.task))
                    self.kwargs = {**obj.defaults, **self.kwargs}  #merge default args
                    jsonschema.validate(self.kwargs, obj.schema)
                    self.kwargs['coords'] = self.coords #add the coordinates to the list of args after validation
            except NameError:
                print(f"ERROR: The task {self.task} specified in the description of {self.name} is not found")
                exit(-1)
            except SyntaxError as e:
                print(f"ERROR: Syntax error in the task specification of {self.name} [{e}]")
                exit(-1)
            except Exception as e:
                print(f"ERROR: Unknown error validating task specification for {self.name} [{e}]")
                exit(-1)

def generateScript(args, placemarks):
    env = jinja2.Environment(loader = jinja2.FileSystemLoader(os.path.join(args.platform, "templates")))
    
    if args.platform == "java":
        ext = "java"
    elif args.platform == "python":
        ext = "py"

    template = env.get_template(f"base.{ext}.jinja2")
    kws = {}
    if args.platform == 'java':
        kws['ip'] = ""
    elif args.platform == 'python':
        if args.sim:
            ip = "10.202.0.1"
        else:
            ip = "192.168.42.1"
        kws['ip'] = ip
    else:
        raise Exception("ERROR: Unsupported drone platform {0}".format(args.platform))

    out = template.render(placemarks=placemarks, platform=args.platform, drone_args=kws)
    return out

def parseKML(args):
    global start

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
                p.description = yaml.load(child.text.strip().replace("<br>", "\n"), Loader=yaml.FullLoader)
            for coord in child.iter(KML_NAMESPACE+'coordinates'):
                p.parseCoordinates(coord)
        placemarks[p.name] = p
        if start is None:
            start = p.coords[0]
    for k,v in placemarks.items():
        v.validate()

    out = generateScript(args, placemarks)

    return out

def _main():
    parser = argparse.ArgumentParser(prog='hermes', 
        description='Convert kml/kmz file to drone-specific instructions.')
    parser.add_argument('input', help='kml/kmz file to convert')
    parser.add_argument('-p', '--platform', choices=['java', 'python'], default='java',
        help='Drone autopilot language to convert to  [default: java (Parrot GroundSDK)]')
    parser.add_argument('-o', '--output', default='./flightplan.ms',
        help='Filename for .ms (mission script) file  [default: ./flightplan.ms]')
    parser.add_argument('-v', '--verbose', action='store_true', 
        help='Write output to console as well [default: False]')
    parser.add_argument('-s', '--sim', action='store_true', 
        help='Connect to  simulated drone instead of a real drone [default: False')

    if len(sys.argv) == 1:
        parser.print_help()
    args = parser.parse_args()
    if(args.verbose):
        print(HR.format("hermes"))
        print(f"Input File:\t\t{args.input}")
        print(f"Drone Control Platform:\t\t{args.platform}")
        print(f"Output File:\t\t{args.output}")

    # Convert the KML specification into a flightscript according to platform
    _, extension = os.path.splitext(args.input)
    if extension == '.kmz':
        print(HR.format("Extracting KMZ"))
        with ZipFile(args.input) as kmz:
            with kmz.open('doc.kml') as kml:
                args.input = kml
                out = parseKML(args)
    else:
        out = parseKML(args)

    if args.platform == "java":
        intermediate = "./java/app/src/main/java/edu/cmu/cs/dronebrain/MS.java"
    elif args.platform == "python":
        intermediate = "./python/MS.py"

    # Write the template output to the intermediate file so that we can compile the flightscript
    with open(intermediate, mode='w', encoding='utf-8') as f:
        f.write(out)
    
    if args.platform == "java":
        try:
            subprocess.run(f"cd java; ./utils/set-env.sh; ./utils/java2dex.sh", shell=True, check=True)
            os.rename("./java/classes.dex", args.output)
            print(HR.format(f"Script {args.output} compiled successfully to converted to dex with d8!"))
        except subprocess.CalledProcessError as e:
            print(e)
    elif args.platform == "python":
        # Package the Python script in an MS folder for shipping
        with ZipFile(args.output, 'w') as zf:
            zf.write("./python/MS.py")
            for file in os.listdir('./python/task_defs/'):
                zf.write(f"./python/task_defs/{file}")
            os.system("cd ./python; pipreqs . --force")
            zf.write("./python/requirements.txt")

    if args.verbose:
        print(HR.format(f"Output for {args.platform}"))
        print(out)

if __name__ == "__main__":
    _main()
