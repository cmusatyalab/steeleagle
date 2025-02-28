import asyncio
import os
import sys

import nest_asyncio
from cnc_protocol import cnc_pb2
from gabriel_client.websocket_client import ProducerWrapper, WebsocketClient
from gabriel_protocol import gabriel_pb2

nest_asyncio.apply()

class Dummy:
    
    def __init__(self, gabriel_server, gabriel_port):
        self.gabriel_server = gabriel_server
        self.gabriel_port = gabriel_port
        self.heartbeats = 0
        self.drone_id = "test_drone"
        
    def processResults(self, result_wrapper):
        if result_wrapper.result_producer_name.value == 'telemetry':
            print(f'Telemetry received: {result_wrapper}')

    def get_producer_wrappers(self):
        async def producer():
            await asyncio.sleep(0)
            self.heartbeats += 1
            input_frame = gabriel_pb2.InputFrame()
            input_frame.payload_type = gabriel_pb2.PayloadType.TEXT
            input_frame.payloads.append('heartbeart'.encode('utf8'))

            extras = cnc_pb2.Extras()
            # test
            extras.drone_id = self.drone_id

            # Register on the first frame
            if self.heartbeats == 1:
                extras.registering = True

            print('Producing Gabriel frame!')
            input_frame.extras.Pack(extras)
            return input_frame

        return ProducerWrapper(producer=producer, source_name='telemetry')
    
    async def run(self):
        print('Creating client')
        gabriel_client = WebsocketClient(
            self.gabriel_server, self.gabriel_port,
            [self.get_producer_wrappers()],  self.processResults
        )
        print('client created')
        
        try:
            # command_coroutine = asyncio.create_task(self.command_handler())
            # telemetry_coroutine = asyncio.create_task(self.telemetry_handler())
            gabriel_client.launch()
            # while True:
            #     # logger.info('Running Kernel')
            #     await asyncio.sleep(0)
                
        except KeyboardInterrupt:
            print("Shutting down Kernel")
            # command_coroutine.cancel()
            # telemetry_coroutine.cancel()
            # await command_coroutine
            # await telemetry_coroutine
            sys.exit(0)
            
if __name__ == "__main__":
    print("Starting Kernel")
    
    gabriel_server = os.environ.get('STEELEAGLE_GABRIEL_SERVER')
    print(f'Gabriel server: {gabriel_server}')
    gabriel_port = os.environ.get('STEELEAGLE_GABRIEL_PORT')
    print(f'Gabriel port: {gabriel_port}')
    k = Dummy(gabriel_server, gabriel_port)
    asyncio.run(k.run())
        