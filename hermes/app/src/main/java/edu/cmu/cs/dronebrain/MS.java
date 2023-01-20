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
import edu.cmu.cs.dronebrain.SimpleTask;

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
            String json = "";
            taskQueue = new PriorityQueue<Task>(1, comp);
            // Task1/SimpleTask START //
            json = "{'coords': [{'lng': -79.949659, 'lat': 40.4135201, 'alt': 15.0}, {'lng': -79.9495826, 'lat': 40.4135161, 'alt': 15.0}, {'lng': -79.949364, 'lat': 40.413464, 'alt': 15.0}, {'lng': -79.9486344, 'lat': 40.4135641, 'alt': 15.0}, {'lng': -79.9486344, 'lat': 40.4136611, 'alt': 15.0}, {'lng': -79.9491213, 'lat': 40.4136172, 'alt': 15.0}, {'lng': -79.9492956, 'lat': 40.4136662, 'alt': 15.0}, {'lng': -79.9494887, 'lat': 40.41366, 'alt': 15.0}, {'lng': -79.9495598, 'lat': 40.4135804, 'alt': 15.0}, {'lng': -79.949659, 'lat': 40.4135201, 'alt': 15.0}]}";
            kwargs.clear();
            kwargs.put("coords", "[{'lng': -79.949659, 'lat': 40.4135201, 'alt': 15.0}, {'lng': -79.9495826, 'lat': 40.4135161, 'alt': 15.0}, {'lng': -79.949364, 'lat': 40.413464, 'alt': 15.0}, {'lng': -79.9486344, 'lat': 40.4135641, 'alt': 15.0}, {'lng': -79.9486344, 'lat': 40.4136611, 'alt': 15.0}, {'lng': -79.9491213, 'lat': 40.4136172, 'alt': 15.0}, {'lng': -79.9492956, 'lat': 40.4136662, 'alt': 15.0}, {'lng': -79.9494887, 'lat': 40.41366, 'alt': 15.0}, {'lng': -79.9495598, 'lat': 40.4135804, 'alt': 15.0}, {'lng': -79.949659, 'lat': 40.4135201, 'alt': 15.0}]");
            taskQueue.add(new SimpleTask(drone, cloudlet, kwargs));
            //taskQueue.add(new SimpleTask(drone, cloudlet, json));

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