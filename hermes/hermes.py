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
    env = jinja2.Environment(loader = jinja2.FileSystemLoader("templates"))
    template = env.get_template(args.template)
    kws = {}
    if args.platform == 'anafi':
        if args.sim:
            ip = "10.202.0.1"
        elif args.controller:
            ip = "192.168.53.1"
        else:
            ip = "192.168.42.1"
        kws['ip'] = ip
    elif args.platform == 'dji':
        kws['ip'] = ""
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

    # TODO: Need to update this for the new simulator.
    if args.sim:
        pass

    return out

def _main():
    parser = argparse.ArgumentParser(prog='hermes', 
        description='Convert kml/kmz file to drone-specific instructions.')
    parser.add_argument('input', help='kml/kmz file to convert')
    parser.add_argument('-p', '--platform', choices=['anafi', 'dji'], default='anafi',
        help='Drone platform to convert to  [default: Anafi]')
    parser.add_argument('-i', '--intermediate', default='./app/src/main/java/edu/cmu/cs/dronebrain/MS.java',
        help='Filename for generated drone instructions [default: ./app/src/main/java/edu/cmu/cs/dronebrain/MS.java]')
    parser.add_argument('-o', '--output', default='./flightplan.dex',
        help='Filename for .dex file  [default: ./flightplan.dex]')
    parser.add_argument('-v', '--verbose', action='store_true', 
        help='Write output to console as well [default: False]')
    parser.add_argument('-t', '--template', default='base.java.jinja2',
        help='Specify a jinja2 template [default: base.java.jinja2]')
    parser.add_argument('-w', '--world_template', default='empty.world.jinja2',
        help='Specify a jinja2 template [default: empty.world.jinja2]')
    parser.add_argument('-wo', '--world_output', default='sim.world',
        help='Specify a world output file [default: sim.world]')
    parser.add_argument('-da', '--dashboard_address', default='steel-eagle-dashboard.pgh.cloudapp.azurelel.cs.cmu.edu',
        help='Specify address of dashboard to send heartbeat to [default: steel-eagle-dashboard.pgh.cloudapp.azurelel.cs.cmu.edu]')
    parser.add_argument('-dp', '--dashboard_port', default='8080',
        help='Specify dashboard port [default: 8080]')
    parser.add_argument('-s', '--sim', action='store_true', 
        help='Connect to  simulated drone at 10.202.0.1 [default: Direct connection to drone at 192.168.42.1]')
    parser.add_argument('-sa', '--sample', action='store_true', default=0.2,
        help='Sample rate for transponder/log file')
    parser.add_argument('-c', '--controller', action='store_true', 
        help='Connect to drone via SkyController at 192.168.53.1 [default: Direct connection to drone at 192.168.42.1]')

    #java2dex.sh options
    parser.add_argument('-jc', '--javac_path', default='~/android-studio/jre/bin/javac',
        help='Specify a the path to javac [default: ~/android-studio/jre/bin/javac]')
    parser.add_argument('-d8', '--d8_path', default='~/Android/Sdk/build-tools/30.0.3/d8',
        help='Specify a the path to d8 [default: ~/Android/Sdk/build-tools/30.0.3/d8]')
    parser.add_argument('-a', '--android_jar', default='~/Android/Sdk/platforms/android-30/android.jar',
        help='Specify a the path to Android SDK jar [default: ~/Android/Sdk/platforms/android-30/android.jar]')

    if len(sys.argv) == 1:
        parser.print_help()
    args = parser.parse_args()
    if(args.verbose):
        print(HR.format("hermes"))
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

    with open(args.intermediate, mode='w', encoding='utf-8') as f:
        f.write(out)
    try:
        subprocess.run(f"./utils/java2dex.sh {args.javac_path} {args.d8_path} {args.android_jar}", shell=True, check=True)
        #java2dex creates classes.dex in src, so we need to rename it if -o was given
        os.rename("./classes.dex", args.output)
        print(HR.format(f"Script {args.output} compiled successfully to converted to dex with d8!"))
    except subprocess.CalledProcessError as e:
        print(e)

    if args.verbose:
        print(HR.format(f"Output for {args.platform}"))
        print(out)

if __name__ == "__main__":
    _main()
