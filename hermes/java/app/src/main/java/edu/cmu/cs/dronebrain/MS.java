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
import edu.cmu.cs.dronebrain.DetectTask;

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
            // Detect/DetectTask START //
            kwargs.clear();
            kwargs.put("gimbal_pitch", "-45.0");
            kwargs.put("drone_rotation", "0.0");
            kwargs.put("sample_rate", "2");
            kwargs.put("hover_delay", "5");
            kwargs.put("model", "coco");
            kwargs.put("coords", "[{'lng': -79.9504103, 'lat': 40.4158558, 'alt': 15.0}, {'lng': -79.9502949, 'lat': 40.4154147, 'alt': 15.0}, {'lng': -79.9498068, 'lat': 40.4154984, 'alt': 15.0}, {'lng': -79.9499784, 'lat': 40.4160028, 'alt': 15.0}, {'lng': -79.9504103, 'lat': 40.4158558, 'alt': 15.0}]");
	    Log.d("MS", "Adding task DetectTask to the task queue!");
            taskQueue.add(new DetectTask(drone, cloudlet, kwargs));

	    Log.d("MS", "Taking off!");
            drone.connect();
            drone.takeOff();
	    Log.d("MS", "Starting mission...");
	    execLoop();
	} catch (Exception e) {
            Log.e("MS", e.toString());
	}
    }

    @Override
    public void pause() {}
}