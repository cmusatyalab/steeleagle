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
import java.util.PriorityQueue;
import java.util.Comparator;
import edu.cmu.cs.dronebrain.interfaces.CloudletItf;
import edu.cmu.cs.dronebrain.interfaces.DroneItf;
import edu.cmu.cs.dronebrain.interfaces.FlightScript;
import edu.cmu.cs.dronebrain.interfaces.Task;

import edu.cmu.cs.dronebrain.TrackingTask;
import edu.cmu.cs.dronebrain.AltitudeTask;

public class MS extends FlightScript {
    
    @Override
    public void run() {
        Comparator<Task> comp = new Comparator<Task>() {
            @Override
            public int compare(Task t1, Task t2) {
                return 0;
            }
        };
        taskQueue = new PriorityQueue<Task>();
	    //taskQueue.add(new AltitudeTask(drone, cloudlet, 15.0));
	    taskQueue.add(new TrackingTask(drone, cloudlet));
	    try {
            drone.connect();
            drone.takeOff();
            drone.moveBy(0.0, 0.0, -15.0);
            drone.setGimbalPose(0.0, -30.0, 0.0);
            drone.startStreaming(480);
            cloudlet.startStreaming(drone, "robomaster", 1);
            //drone.rotateBy(-60.0);
            //drone.setGimbalPose(0.0, -30.0, 0.0);
	        execLoop();
	    } catch (Exception e) {
            return;        
	    }
    }
    
    @Override
    public void pause() {}
}