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
            // AvoidancePath/ObstacleTask START //
            kwargs.clear();
            kwargs.put("model", "DPT_BEiT_L_512");
            kwargs.put("speed", "5");
            kwargs.put("altitude", "52.0");
            kwargs.put("coords", "[{'lng': 2.3676097, 'lat': 48.8789323, 'alt': 15.0}, {'lng': 2.3669914, 'lat': 48.8789235, 'alt': 15.0}]");
            taskQueue.add(new ObstacleTask(drone, cloudlet, kwargs));
            // AvoidancePath2/ObstacleTask START //
            kwargs.clear();
            kwargs.put("model", "DPT_BEiT_L_512");
            kwargs.put("speed", "5");
            kwargs.put("altitude", "52.0");
            kwargs.put("coords", "[{'lng': 2.3669292, 'lat': 48.8788794, 'alt': 15.0}, {'lng': 2.3676105, 'lat': 48.8789218, 'alt': 15.0}]");
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