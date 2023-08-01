from implementation.drones import ParrotAnafi
import time

if __name__ == "__main__":
    kwargs = {'ip': '10.202.0.1'}
    drone = ParrotAnafi.ParrotAnafi(**kwargs)
    drone.connect()
    print(drone.isConnected())
    drone.takeOff()
    time.sleep(2)
    drone.kill()
    drone.moveBy(0.0, 10.0, 0.0, 0.0)
    drone.land()
