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

KML_NAMESPACE = '{http://www.opengis.net/kml/2.2}'
HR = '==============={0}===================='
FIXED_ALTITUDE = 6.0 #meters

def generateOlympeScript(args, coords):

    env = jinja2.Environment(loader = jinja2.FileSystemLoader("templates"))
    template = env.get_template(args.template)
    out = template.render(coords=parseCoordinates(coords))
    return out

def parseCoordinates(coords):
    '''
    <coordinates>
        long0,lat0,altitude0
        ...
        longN,latN,altitudeN
    </coordinates>
    '''
    for c in coords:
        for line in c.text.strip().split('\n'):
            stripped = line.strip()
            lng,lat,alt = stripped.split(',')
            yield {'lng': lng, 'lat': lat, 'alt': FIXED_ALTITUDE if float(alt) < 1 else alt}

def parseKML(args):
    print(HR.format("Parsing KML"))
    tree = ET.parse(args.input)
    root = tree.getroot()
    coords = []
    out = ""
    for placemark in root.iter(KML_NAMESPACE+'Placemark'):
        for child in placemark:
            if args.verbose and child.tag == KML_NAMESPACE+'name':
                print(f"Processing placemark named {child.text.strip()}...")
            for coord in child.iter(KML_NAMESPACE+'coordinates'):
                coords.append(coord)

    if args.platform == 'anafi':
        out = generateOlympeScript(args, coords)
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
        help='Filename for generated drone instructions [default: drone.txt]')
    parser.add_argument('-v', '--verbose', action='store_true', 
        help='Write output to console as well [default: False]')
    parser.add_argument('-t', '--template', default='anafi.py.jinja2',
        help='Specify a jinja2 template [default: anafi.py.jinja2]')

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
