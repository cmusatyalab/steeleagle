#!/usr/bin/env python3
import argparse
import logging
import os
import cv2
import asyncio
import time
from gabriel_protocol import gabriel_pb2
from gabriel_client.zeromq_client import ProducerWrapper, ZeroMQClient
import gabriel_extras_pb2 as gabriel_extras
from gabriel_server import cognitive_engine

logging.basicConfig(level=logging.DEBUG) 
logger = logging.getLogger(__name__)

class SlamZeroMQClient:
    def __init__(self, image_path, server="gabriel-server", port=9099, source_name="telemetry", client_id="slam_client"):
        self.source_name = source_name
        self.server = server
        self.port = port
        self.client_id = client_id
        
        # Store the latest results from each engine
        self.engine_results = {}
        
        # Setup image source
        if os.path.isdir(image_path):
            self.image_files = sorted([os.path.join(image_path, f)
                                      for f in os.listdir(image_path)
                                      if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
            if not self.image_files:
                raise ValueError(f"No image files found in {image_path}")
            logger.info(f"Found {len(self.image_files)} images")
            self.idx = 0
            self.is_dir = True
        else:
            self.image = cv2.imread(image_path)
            if self.image is None:
                raise ValueError(f"Cannot read {image_path}")
            self.is_dir = False
        
        # Setup ZeroMQ client
        self.gabriel_client = ZeroMQClient(
            self.server, self.port,
            [self.get_image_producer()], self.process_results
        )

    def process_results(self, result_wrapper):
        if len(result_wrapper.results) == 0:
            return
            
        # Get engine ID
        engine_id = result_wrapper.result_producer_name.value
        logger.info(f"Received {len(result_wrapper.results)} results from engine: {engine_id}")
        
        # Process each result
        for result in result_wrapper.results:
            if result.payload_type == gabriel_pb2.PayloadType.TEXT:
                payload = result.payload.decode('utf-8')
                # Save result for the corresponding engine
                timestamp = time.time()
                self.engine_results[engine_id] = {
                    'payload': payload,
                    'timestamp': timestamp
                }
                
                # Process results differently based on engine type
                if "terra-slam" in engine_id.lower():
                    logger.info(f"SLAM result: {payload}")
                # else:
                #     logger.debug(f"Other engine result ({engine_id}): {payload}")
            else:
                logger.info(f"Got non-text result type {result.payload_type} from {engine_id}")
    
    def get_image_producer(self):
        async def producer():
            await asyncio.sleep(0.1)
            
            logger.debug(f"Image producer: starting at {time.time()}")
            input_frame = gabriel_pb2.InputFrame()
            
            try:
                if self.is_dir:
                    img_path = self.image_files[self.idx]
                    img = cv2.imread(img_path)
                    self.idx = (self.idx + 1) % len(self.image_files)
                    logger.info(f"Sending {img_path}")
                else:
                    img = self.image
                
                _, jpg_buffer = cv2.imencode('.jpg', img)
                input_frame.payload_type = gabriel_pb2.PayloadType.IMAGE
                input_frame.payloads.append(jpg_buffer.tobytes())
                
                # Add extras similar to GabrielCompute.py
                extras = gabriel_extras.Extras()
                # extras.drone_id = self.client_id
                extras.telemetry.drone_name = self.client_id
                
                # Add telemetry data (avoid using fields that don't exist)
                telemetry = extras.telemetry
                # Only set compatible fields
                telemetry.uptime.FromSeconds(0)  # Mock uptime
                
                # Set computation request in the same way as GabrielCompute
                # Note: In GabrielCompute, compute_id is passed as the key, not specifying a specific engine
                compute_command = extras.cpt_request
                compute_command.cpt.model = "terra-slam"  # Request terra-slam engine
                
                # Pack extras into the input frame
                input_frame.extras.Pack(extras)
                
                logger.debug(f"Image producer: finished preparing frame at {time.time()}")
            except Exception as e:
                input_frame.payload_type = gabriel_pb2.PayloadType.TEXT
                input_frame.payloads.append(f"Unable to produce a frame: {e}".encode('utf-8'))
                logger.error(f'Image producer: unable to produce a frame: {e}')
                
            return input_frame
            
        return ProducerWrapper(producer=producer, source_name=self.source_name)
    
    def print_all_results(self):
        """Print the latest results from all engines"""
        logger.info("==== Current Results from All Engines ====")
        for engine, data in self.engine_results.items():
            logger.info(f"Engine: {engine}, Time: {data['timestamp']}")
            logger.info(f"Payload: {data['payload'][:100]}...")
        logger.info("=========================================")
    
    async def run(self):
        logger.info(f"Starting ZeroMQ client connecting to {self.server}:{self.port}")
        logger.info(f"Will collect results from all available engines")
        await self.gabriel_client.launch_async()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-i", "--image", required=True, help="image file or directory")
    ap.add_argument("-s", "--server", default="gabriel-server", help="server host")
    ap.add_argument("-p", "--port", type=int, default=9099, help="server port")
    ap.add_argument("-n", "--name", default="telemetry", help="source name")
    ap.add_argument("-c", "--client_id", default="slam_client", help="client id for drone_id")
    args = ap.parse_args()

    client = SlamZeroMQClient(
        image_path=args.image,
        server=args.server,
        port=args.port,
        source_name=args.name,
        client_id=args.client_id
    )
    
    asyncio.run(client.run())

if __name__ == "__main__":
    main()