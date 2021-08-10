#/usr/bin/python3
import olympe
from olympe.messages.ardrone3.Piloting import TakeOff, Landing, moveTo
import olympe.enums.move as mode
from olympe.messages.ardrone3.PilotingState import FlyingStateChanged, moveToChanged

if __name__ == "__main__":
        
    #eventually IP will be specified depending on what drone is chosen
    IP = "10.202.0.1" 
    drone = olympe.Drone(IP)
    drone.connect()
    drone(TakeOff()).wait().success()
    
    drone(
        moveTo(40.415169, -79.94897, 6.0, mode.orientation_mode.to_target, 0.0)
        >> moveToChanged(latitude=40.415169, longitude=-79.94897, altitude=6.0, orientation_mode=mode.orientation_mode.to_target, status='DONE')
    ).wait().success()
    
    drone(
        moveTo(40.4157082, -79.9492543, 6.0, mode.orientation_mode.to_target, 0.0)
        >> moveToChanged(latitude=40.4157082, longitude=-79.9492543, altitude=6.0, orientation_mode=mode.orientation_mode.to_target, status='DONE')
    ).wait().success()
    
    drone(
        moveTo(40.4156265, -79.9496244, 6.0, mode.orientation_mode.to_target, 0.0)
        >> moveToChanged(latitude=40.4156265, longitude=-79.9496244, altitude=6.0, orientation_mode=mode.orientation_mode.to_target, status='DONE')
    ).wait().success()
    
    drone(
        moveTo(40.4153978, -79.9495064, 6.0, mode.orientation_mode.to_target, 0.0)
        >> moveToChanged(latitude=40.4153978, longitude=-79.9495064, altitude=6.0, orientation_mode=mode.orientation_mode.to_target, status='DONE')
    ).wait().success()
    
    drone(
        moveTo(40.4152548, -79.9500375, 6.0, mode.orientation_mode.to_target, 0.0)
        >> moveToChanged(latitude=40.4152548, longitude=-79.9500375, altitude=6.0, orientation_mode=mode.orientation_mode.to_target, status='DONE')
    ).wait().success()
    
    drone(
        moveTo(40.4149403, -79.9499087, 6.0, mode.orientation_mode.to_target, 0.0)
        >> moveToChanged(latitude=40.4149403, longitude=-79.9499087, altitude=6.0, orientation_mode=mode.orientation_mode.to_target, status='DONE')
    ).wait().success()
    
    drone(
        moveTo(40.415169, -79.94897, 6.0, mode.orientation_mode.to_target, 0.0)
        >> moveToChanged(latitude=40.415169, longitude=-79.94897, altitude=6.0, orientation_mode=mode.orientation_mode.to_target, status='DONE')
    ).wait().success()
    
    drone(Landing()).wait().success()
    drone.disconnect()