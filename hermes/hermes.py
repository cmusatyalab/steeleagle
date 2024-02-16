#!/usr/bin/env python3

# Copyright 2021-2022 Carnegie Mellon University
# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import os
import sys
import argparse
from zipfile import ZipFile
import subprocess

KML_NAMESPACE = '{http://www.opengis.net/kml/2.2}'
HR = '==============={0}===================='
FIXED_ALTITUDE = 25.0 #meters
start = None #starting position, to be assigned


def _main():
    parser = argparse.ArgumentParser(prog='hermes', 
        description='Convert kml/kmz file to drone-specific instructions.')
    # parser.add_argument('input', help='kml/kmz file to convert')
    parser.add_argument('-p', '--platform', choices=['java', 'python'], default='python',
        help='Drone autopilot language to convert to  [default: java (Parrot GroundSDK)]')
    parser.add_argument('-o', '--output', default='./flightplan.ms',
        help='Filename for .ms (mission script) file  [default: ./flightplan.ms]')
    parser.add_argument('-v', '--verbose', action='store_true', 
        help='Write output to console as well [default: False]')

    if len(sys.argv) == 1:
        parser.print_help()
    args = parser.parse_args()
    if(args.verbose):
        print(HR.format("hermes"))
        print(f"Drone Control Platform:\t\t{args.platform}")
        print(f"Output File:\t\t{args.output}")
    
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
            for file in os.listdir('./python/runtime/'):
                zf.write(f"./python/runtime/{file}")
            for file in os.listdir('./python/transition_defs/'):
                zf.write(f"./python/transition_defs/{file}")
            os.system("cd ./python; pipreqs . --force")
            zf.write("./python/requirements.txt")

    if args.verbose:
        print(HR.format(f"Output for {args.platform}"))

if __name__ == "__main__":
    _main()
