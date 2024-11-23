#!/usr/bin/env python3

# Copyright (C) 2024 Carnegie Mellon University
# SPDX-FileCopyrightText: 2024 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import json
import os
import subprocess
import sys
import logging
from zipfile import ZipFile
from google.protobuf.message import DecodeError
from google.protobuf import text_format
import requests
from cnc_protocol import cnc_pb2
import argparse
import zmq
import zmq.asyncio
import redis
from urllib.parse import urlparse


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Set up the paths and variables for the compiler
compiler_path = '/compiler'
compiler_file = 'compile-1.5-full.jar'
output_path = '/compiler/out/flightplan_'
platform_path  = '/compiler/python/project'


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
    

        
def send_to_drone(msg, base_url, drone_list, cmd_front_cmdr_sock, redis):
    try:
        logger.info(f"Sending request to drone...")
        # Send the command to each drone 
        for drone_id in drone_list:
            # check if the cmd is a mission
            if (base_url):
                # reconstruct the script url with the correct compiler output path
                msg.cmd.script_url = f"{base_url}{output_path}{drone_id}.ms"
                logger.info(f"script url:  {msg.cmd.script_url}")
            
            # send the command to the drone
            cmd_front_cmdr_sock.send_multipart([drone_id.encode('utf-8'), msg.SerializeToString()])
            logger.info(f'Delivered request to drone {drone_id}:\n {text_format.MessageToString(msg)}')
            
            # store the record in redis
            key = redis.xadd(
                f"commands",
                {"commander": msg.commander_id, "drone": drone_id, "value": text_format.MessageToString(msg),}
            )
            logger.debug(f"Updated redis under stream commands at key {key}")
    except Exception as e:
        logger.error(f"Error sending request to drone: {e}")

    
def listen_cmdrs(cmdr_sock, cmd_front_cmdr_sock, redis, alt):
    while True:
        
        # Listen for incoming requests from cmdr
        req = cmdr_sock.recv()
        try:
            msg = cnc_pb2.Extras()
            msg.ParseFromString(req)
            logger.info(f'Request received:\n{text_format.MessageToString(msg)}')
        except DecodeError:
            cmdr_sock.send(b'Error decoding protobuf. Did you send a cnc_pb2?')
            logger.info(f'Error decoding protobuf. Did you send a cnc_pb2?')
            continue
        
        # get the drone list
        try:
            drone_list_json = msg.cmd.for_drone_id
            drone_list = json.loads(drone_list_json)
            logger.info(f"drone list:  {drone_list}")
        except json.JSONDecodeError:
            cmdr_sock.send(b'Error decoding drone list. Did you send a JSON list?')
            logger.info(f'Error decoding drone list. Did you send a JSON list?')
            continue
            
        # Check if the command contains a mission and compile it if true
        base_url = None
        if (msg.cmd.script_url):
            # download the script
            script_url = msg.cmd.script_url
            logger.info(f"script url:  {script_url}")
            dsl, kml = download_script(script_url)
            
            # compile the mission
            drone_list_revised = "&".join(drone_list)
            logger.info(f"drone list revised:  {drone_list_revised}")
            compile_mission(dsl, kml, drone_list_revised, alt)
            
            # get the base url
            parsed_url = urlparse(script_url)
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"

            
        # send the command to the drone
        send_to_drone(msg, base_url, drone_list, cmd_front_cmdr_sock, redis)
            

             
        cmdr_sock.send(b'ACK')
        logger.info('Sent ACK to commander')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--droneport', type=int, default=5003, help='Specify port to listen for drone requests [default: 5003]')
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
    
    # Set the altitude
    alt = args.altitude
    logger.info(f"Starting control plane with altitude {alt}...")
    
    # Connect to redis
    r = redis.Redis(host='redis', port=args.redis, username='steeleagle', password=f'{args.auth}',decode_responses=True)
    logger.info(f"Connected to redis on port {args.redis}...")

    # Set up the commander socket
    ctx = zmq.Context()
    cmdr_sock = ctx.socket(zmq.REP)
    cmdr_sock.bind(f'tcp://*:{args.cmdrport}')
    logger.info(f'Listening on tcp://*:{args.cmdrport} for commander requests...')

    # Set up the drone socket
    async_ctx = zmq.asyncio.Context()
    cmd_front_cmdr_sock = async_ctx.socket(zmq.ROUTER)
    cmd_front_cmdr_sock.setsockopt(zmq.ROUTER_HANDOVER, 1)
    cmd_front_cmdr_sock.bind(f'tcp://*:{args.droneport}')
    logger.info(f'Listening on tcp://*:{args.droneport} for drone requests...')
    
    # Listen for incoming requests from cmdr
    try:
        listen_cmdrs(cmdr_sock, cmd_front_cmdr_sock, r, alt)
    except KeyboardInterrupt:
        logger.info('Shutting down...')
        cmdr_sock.close()
        cmd_front_cmdr_sock.close()

if __name__ == '__main__':
    main()