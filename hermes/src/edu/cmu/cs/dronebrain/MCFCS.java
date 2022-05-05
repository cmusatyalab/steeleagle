/* Copyright 2022 Carnegie Mellon University

 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

      http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License. 
*/


package edu.cmu.cs.dronebrain;

import java.lang.Thread;
import edu.cmu.cs.dronebrain.interfaces.Cloudlet;
import edu.cmu.cs.dronebrain.interfaces.Drone;
import edu.cmu.cs.dronebrain.interfaces.FlightScript;

public class MCFCS extends FlightScript{

    private Drone drone;
    private Cloudlet cloudlet;

    public MCFCS() {
        drone = null;
        cloudlet = null;
    }

    public MCFCS(Drone d, Cloudlet c) {
        drone = d;
        cloudlet = c;
     }

    public void run() {
        try {
            drone.connect("192.168.42.1");
            drone.takeOff();
        
            
            // Task/heimdall_TakePhotosAlongPath START
            //{'mode': 'SINGLE', 'interval': 10, 'gimbal_pitch': -45.0, 'drone_rotation': 0.0, 'coords': [{'lng': -79.950074, 'lat': 40.4156115, 'alt': 15.0}, {'lng': -79.9500203, 'lat': 40.4152194, 'alt': 15.0}, {'lng': -79.9492049, 'lat': 40.4153379, 'alt': 15.0}, {'lng': -79.9494356, 'lat': 40.4156891, 'alt': 15.0}, {'lng': -79.950074, 'lat': 40.4156115, 'alt': 15.0}]}
            
    drone.moveTo(40.4156115, -79.950074, 15.0);
    drone.rotateBy(0.0);
    drone.setGimbalPose(0.0, -45.0, 0.0);
    drone.takePhoto();
    
    drone.moveTo(40.4152194, -79.9500203, 15.0);
    drone.rotateBy(0.0);
    drone.setGimbalPose(0.0, -45.0, 0.0);
    drone.takePhoto();
    
    drone.moveTo(40.4153379, -79.9492049, 15.0);
    drone.rotateBy(0.0);
    drone.setGimbalPose(0.0, -45.0, 0.0);
    drone.takePhoto();
    
    drone.moveTo(40.4156891, -79.9494356, 15.0);
    drone.rotateBy(0.0);
    drone.setGimbalPose(0.0, -45.0, 0.0);
    drone.takePhoto();
    
    drone.moveTo(40.4156115, -79.950074, 15.0);
    drone.rotateBy(0.0);
    drone.setGimbalPose(0.0, -45.0, 0.0);
    drone.takePhoto();
    
            //Task/heimdall_TakePhotosAlongPath END
            

            drone.disconnect();

        }
        catch( Exception e) {

        }

    }

}