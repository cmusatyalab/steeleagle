from implementation.drones import ParrotAnafi
import time

if __name__ == "__main__":
    kwargs = {'ip': '192.168.42.1'}
    drone = ParrotAnafi.ParrotAnafi(**kwargs)
    drone.connect()
    print(drone.isConnected())
    drone.PCMD(0, 100, 0, 0)
    drone.disconnect()