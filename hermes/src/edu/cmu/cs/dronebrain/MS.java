// Copyright 2022 Carnegie Mellon University
// SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
//
// SPDX-License-Identifier: GPL-2.0-only

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
