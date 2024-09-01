import asyncio
import os
import time
import zmq
from cnc_protocol import cnc_pb2

context = zmq.Context()
socket = context.socket(zmq.ROUTER)
socket.bind('tcp://' + os.environ.get('STEELEAGLE_DRIVER_COMMAND_ADDR'))

# Create a pub/sub socket that telemetry can be read from
telemetry_socket = context.socket(zmq.PUB)
telemetry_socket.setsockopt(zmq.CONFLATE, 1)
tel_pub_addr = 'tcp://' + os.environ.get('STEELEAGLE_DRIVER_TEL_PUB_ADDR')
if tel_pub_addr:
    telemetry_socket.connect(tel_pub_addr)

# Create a pub/sub socket that the camera stream can be read from
camera_socket = context.socket(zmq.PUB)
camera_socket.setsockopt(zmq.CONFLATE, 1)
cam_pub_addr = 'tcp://' + os.environ.get('STEELEAGLE_DRIVER_CAM_PUB_ADDR')
if cam_pub_addr:
    camera_socket.bind(cam_pub_addr)


async def camera_stream(drone, camera_sock):
    frame_id = 0
    cam_message = cnc_protocol.Frame() 
    while drone.isConnected():
        try:
            cam_message.data = await drone.getVideoFrame()
            cam_message.height = 720
            cam_message.width = 1280
            cam_message.channels = 3
            cam_message.id = frame_id
            frame_id = frame_id + 1 
            camera_sock.send(cam_message.SerializeToString())
            logger.debug('Camera stream: Timestamp: {:%Y-%m-%d %H:%M:%S}'.format(datetime.datetime.now()))
            logger.debug(f'Camera stream: ID: frame_id {frame_id}')
        except Exception as e:
            pass
        await asyncio.sleep(0)

async def telemetry_stream(drone, telemetry_sock):
    logger.info('Starting telemetry stream')
    tel_message = cnc_protocol.Telemetry()
    while drone.isConnected():
        try:
            telDict = await drone.getTelemetry()
            tel_message.global_position.latitude = telDict["gps"][0] 
            tel_message.global_position.longitude = telDict["gps"][1]
            tel_message.global_position.altitude = telDict["gps"][2]
            tel_message.relative_position.up = telDict["relAlt"]
            tel_message.mag = telDict["magnetometer"]
            tel_message.battery = telDict["battery"]
            tel_message.gimbal_attitude.yaw = telDict["gimbalAttitude"]["yaw"]
            tel_message.gimbal_attitude.pitch = telDict["gimbalAttitude"]["pitch"]
            tel_message.gimbal_attitude.roll = telDict["gimbalAttitude"]["roll"]
            tel_message.drone_attitude.yaw = telDict["attitude"]["yaw"]
            tel_message.drone_attitude.pitch = telDict["attitude"]["pitch"]
            tel_message.drone_attitude.roll = telDict["attitude"]["roll"]
            tel_message.velocity.forward_vel = telDict["imu"]["forward"]
            tel_message.velocity.right_vel = telDict["imu"]["right"]
            tel_message.velocity.up_vel = telDict["imu"]["up"]
            tel_message.satellites = telDict["satellites"]
            logger.debug(f"Telemetry: {tel_message}")
            telemetry_sock.send(tel_message.SerializeToString())
            logger.debug('Sent telemetry')
        except Exception as e:
            logger.error(f'Failed to get telemetry, error: {e}')
        await asyncio.sleep(0)
        
class d_server():

    async def a_run(self):    
        while True:
            try:
                # Receive a message from the DEALER socket
                message_parts = socket.recv_multipart(flags=zmq.NOBLOCK)
                
                # Expecting three parts: [identity, empty, message]
                if len(message_parts) != 2:
                    print(f"Invalid message received: {message_parts}")
                    continue
                
                identity = message_parts[0]  # Identity of the DEALER socket
                message = message_parts[1]     # The empty delimiter part
                # message = message_parts[2]   # The actual serialized request
                
                # Print each part to understand the structure
                print(f"Identity: {identity}")
                # print(f"Empty delimiter: {empty}")
                print(f"Message: {message}")
                
                # Parse the message
                driver_req = cnc_pb2.Driver()
                driver_req.ParseFromString(message)
                print(f"Received the message: {driver_req}")
                print(f"Request seqNum: {driver_req.seqNum}")
                
                # Print parsed message and determine the response
                if driver_req.takeOff:
                    print(f"take off received: {time.time()}")
                    print("Request: take Off")
                    driver_req.resp = cnc_pb2.ResponseStatus.COMPLETED
                else:
                    print("Unknown request")
                    driver_req.resp = cnc_pb2.ResponseStatus.NOTSUPPORTED
                
                serialized_response = driver_req.SerializeToString()
                
                # Send a reply back to the client with the identity frame and empty delimiter
                socket.send_multipart([identity, serialized_response])
                
                print(f"done processing request")
            
            except zmq.Again as e:
                pass
            await asyncio.sleep(0)

if __name__ == "__main__":
    print("Starting server")
    d= d_server()
    asyncio.run(d.a_run())