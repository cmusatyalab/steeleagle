#!/usr/bin/env python3

# Copyright (C) 2024 Carnegie Mellon University
# SPDX-FileCopyrightText: 2024 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import copy
import json
import os
import subprocess
import sys
import threading
import time
import logging
from zipfile import ZipFile
from google.protobuf.message import DecodeError
from google.protobuf import text_format
import requests
from cnc_protocol import cnc_pb2
import argparse
import zmq
import redis
from urllib.parse import urlparse

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

interrupt = threading.Event()

compiler_path = '/compiler'
compiler_file = 'compile-1.5-full.jar'
output_path = '/compiler/out/flightplan_'
platform_path  = '/compiler/python'


def download_script(script_url):
    try:
        # Get the ZIP file name from the URL
        filename = script_url.rsplit(sep='/')[-1]
        logger.info(f'Writing {filename} to disk...')
        
        # Download the ZIP file
        r = requests.get(script_url, stream=True)
        with open(filename, mode='wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

        # Variables to hold extracted .dsl and .kml files
        dsl_file = None
        kml_file = None

        # Extract all contents of the ZIP file and remember .dsl and .kml filenames
        with ZipFile(filename, 'r') as z:
            z.extractall(path=compiler_path)
            for file_name in z.namelist():
                if file_name.endswith('.dsl'):
                    dsl_file = file_name
                elif file_name.endswith('.kml'):
                    kml_file = file_name

        # Log or return the results
        logger.info(f"Extracted DSL files: {dsl_file}")
        logger.info(f"Extracted KML files: {kml_file}")
        
        return dsl_file, kml_file

    except Exception as e:
        logger.error(f"Error during download or extraction: {e}")
        
def compile_mission(dsl_file, kml_file, drone_list, alt):
    # Construct the full paths for the DSL and KML files
    dsl_file_path = os.path.join(compiler_path, dsl_file)
    kml_file_path = os.path.join(compiler_path, kml_file)
    jar_path = os.path.join(compiler_path, compiler_file)
    altitude = str(alt)
    
    # Define the command and arguments
    command = [
        "java",
        "-jar", jar_path,
        "-d", drone_list,
        "-s", dsl_file_path,
        "-k", kml_file_path,
        "-o", output_path,
        "-p", platform_path,
        "-a", altitude
    ]
    
    # Run the command
    logger.info(f"Running command: {' '.join(command)}")
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    
    # Log the output
    logger.info(f"Compilation output: {result.stdout}")
    
    # Output the results
    logger.info("Compilation successful.")
    

        
def listen_drones(args, drones):
    ctx = zmq.Context()
    sock = ctx.socket(zmq.REP)
    sock.bind(f'tcp://*:{args.droneport}')
    while not interrupt.isSet():
        msg = sock.recv()
        try:
            extras = cnc_pb2.Extras()
            extras.ParseFromString(msg)
            d = drones[extras.drone_id]
            sock.send(d.SerializeToString())
            logger.info(f'Delivered request:\n{text_format.MessageToString(d)}')
            del drones[extras.drone_id]
        except KeyError:
            sock.send(b'No commands.')
        except DecodeError:
            sock.send(b'Error decoding protobuf. Did you send a cnc_pb2?')
    sock.close()
    
def listen_cmdrs(args, drones, redis, alt):
    ctx = zmq.Context()
    sock = ctx.socket(zmq.REP)
    sock.bind(f'tcp://*:{args.cmdrport}')
    while not interrupt.isSet():
        msg = sock.recv()
        extras = cnc_pb2.Extras()
        
        try:
            extras.ParseFromString(msg)
            logger.info(f'Request received:\n{text_format.MessageToString(extras)}')
        except DecodeError:
            sock.send(b'Error decoding protobuf. Did you send a cnc_pb2?')
            logger.info(f'Error decoding protobuf. Did you send a cnc_pb2?')
            continue
            
        try:
            # assuming the commander also gives drone id in json format 
            drone_list_json = extras.cmd.for_drone_id
            drone_list = json.loads(drone_list_json)
            logger.info(f"drone list:  {drone_list}")
        except json.JSONDecodeError:
            sock.send(b'Error decoding drone list. Did you send a JSON list?')
            logger.info(f'Error decoding drone list. Did you send a JSON list?')
            continue
            
        # Check if the command contains a mission and process it
        base_url = None
        if (extras.cmd.script_url):
            # download the script
            script_url = extras.cmd.script_url
            logger.info(f"script url:  {script_url}")
            dsl, kml = download_script(script_url)
            
            # compile the mission
            drone_list_revised = "&".join(drone_list)
            logger.info(f"drone list revised:  {drone_list_revised}")
            compile_mission(dsl, kml, drone_list_revised, alt)
            
            # get the base url
            parsed_url = urlparse(script_url)
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"

            
        # Send the command to each drone 
        for drone_id in drone_list:
            extras_copy = copy.deepcopy(extras)
            
            # check if the cmd is a mission
            if (base_url):
                # reconstruct the script url with the correct compiler output path
                extras_copy.cmd.script_url = f"{base_url}{output_path}{drone_id}.ms"
                logger.info(f"script url:  {extras_copy.cmd.script_url}")
                
            # store the command in drones dict and redis
            drones[drone_id] = extras_copy
            key = redis.xadd(
                f"commands",
                {"commander": extras.commander_id, "drone": drone_id, "value": text_format.MessageToString(extras_copy),}
            )
            logger.debug(f"Updated redis under stream commands at key {key}")
             
        sock.send(b'ACK')
        
        
    sock.close()
    

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--droneport', type=int, default=6000, help='Specify port to listen for drone requests [default: 6000]')
    parser.add_argument('-c', '--cmdrport', type=int, default=6001, help='Specify port to listen for commander requests [default: 6001]')
    parser.add_argument(
        "-r", "--redis", type=int, default=6379, help="Set port number for redis connection [default: 6379]"
    )
    parser.add_argument(
        "-a", "--auth", default="", help="Share key for redis user."
    )
    parser.add_argument(
        "--altitude", type=int, default=15, help="base altitude for the drones mission"
    )
    args = parser.parse_args()
    alt = args.altitude
    r = redis.Redis(host='redis', port=args.redis, username='steeleagle', password=f'{args.auth}',decode_responses=True)
    logger.info(f"Connected to redis on port {args.redis}...")
    drones = {}

    logger.info(f'Listening on tcp://*:{args.droneport} for drone requests...')
    logger.info(f'Listening on tcp://*:{args.cmdrport} for commander requests...')
    
    d = threading.Thread(target=listen_drones, args=[args, drones])
    c = threading.Thread(target=listen_cmdrs, args=[args, drones, r, alt])
    d.start()
    c.start()

    try:
        while d.is_alive():
            time.sleep(0.1)
    except KeyboardInterrupt:
        interrupt.set()
        logging.info("Waiting for threads to join...")
        c.join()
        d.join()

if __name__ == '__main__':
    main()