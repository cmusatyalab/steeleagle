// SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
//
// SPDX-License-Identifier: GPL-2.0-only

package edu.cmu.cs.dronebrain;

import java.lang.Thread;
import java.util.PriorityQueue;
import java.util.Comparator;
import java.util.HashMap;
import edu.cmu.cs.dronebrain.interfaces.CloudletItf;
import edu.cmu.cs.dronebrain.interfaces.DroneItf;
import edu.cmu.cs.dronebrain.interfaces.FlightScript;
import edu.cmu.cs.dronebrain.interfaces.Task;
import android.util.Log;

// import derived tasks
import edu.cmu.cs.dronebrain.ObstacleTask;
import edu.cmu.cs.dronebrain.ObstacleTask;

public class MS extends FlightScript {
    
    @Override
    public void run() {

        Comparator<Task> comp = new Comparator<Task>() {
            @Override
            public int compare(Task t1, Task t2) {
                return 0;
            }
        };
        try {
            HashMap<String, String> kwargs =  new HashMap<String, String>();
            taskQueue = new PriorityQueue<Task>(1, comp);
            // Avoid1/ObstacleTask START //
            kwargs.clear();
            kwargs.put("model", "DPT_Large");
            kwargs.put("speed", "10");
            kwargs.put("altitude", "52.0");
            kwargs.put("coords", "[{'lng': -79.9611343, 'lat': 40.428706, 'alt': 15.0}, {'lng': -79.9603994, 'lat': 40.428022, 'alt': 15.0}]");
            taskQueue.add(new ObstacleTask(drone, cloudlet, kwargs));
            // Avoid2/ObstacleTask START //
            kwargs.clear();
            kwargs.put("model", "DPT_Large");
            kwargs.put("speed", "10");
            kwargs.put("altitude", "52.0");
            kwargs.put("coords", "[{'lng': -79.95993, 'lat': 40.4282537, 'alt': 15.0}, {'lng': -79.9607105, 'lat': 40.4289296, 'alt': 15.0}]");
            taskQueue.add(new ObstacleTask(drone, cloudlet, kwargs));

            drone.connect();
            drone.takeOff();
	        execLoop();
	    } catch (Exception e) {
            Log.i("FlightScript", e.toString());
	    }
    }

    @Override
    public void pause() {}
}