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

// import derived tasks
import edu.cmu.cs.dronebrain.TrackingTask;
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
        HashMap<String, String> kwargs =  new HashMap();
        String json = "";
        taskQueue = new PriorityQueue<Task>(1, comp);
        // Task1/TrackingTask START //
        json = "{'gimbal_pitch': -30.0, 'drone_rotation': 0.0, 'hover_delay': 10, 'model': 'robomaster', 'class': 'person', 'coords': [{'lng': -79.949659, 'lat': 40.4135201, 'alt': 15.0}, {'lng': -79.9495826, 'lat': 40.4135161, 'alt': 15.0}, {'lng': -79.949364, 'lat': 40.413464, 'alt': 15.0}, {'lng': -79.9486344, 'lat': 40.4135641, 'alt': 15.0}, {'lng': -79.9486344, 'lat': 40.4136611, 'alt': 15.0}, {'lng': -79.9491213, 'lat': 40.4136172, 'alt': 15.0}, {'lng': -79.9492956, 'lat': 40.4136662, 'alt': 15.0}, {'lng': -79.9494887, 'lat': 40.41366, 'alt': 15.0}, {'lng': -79.9495598, 'lat': 40.4135804, 'alt': 15.0}, {'lng': -79.949659, 'lat': 40.4135201, 'alt': 15.0}]}";
        kwargs.clear();
        kwargs.put("gimbal_pitch", "-30.0");
        kwargs.put("drone_rotation", "0.0");
        kwargs.put("hover_delay", "10");
        kwargs.put("model", "robomaster");
        kwargs.put("class", "person");
        kwargs.put("coords", "[{'lng': -79.949659, 'lat': 40.4135201, 'alt': 15.0}, {'lng': -79.9495826, 'lat': 40.4135161, 'alt': 15.0}, {'lng': -79.949364, 'lat': 40.413464, 'alt': 15.0}, {'lng': -79.9486344, 'lat': 40.4135641, 'alt': 15.0}, {'lng': -79.9486344, 'lat': 40.4136611, 'alt': 15.0}, {'lng': -79.9491213, 'lat': 40.4136172, 'alt': 15.0}, {'lng': -79.9492956, 'lat': 40.4136662, 'alt': 15.0}, {'lng': -79.9494887, 'lat': 40.41366, 'alt': 15.0}, {'lng': -79.9495598, 'lat': 40.4135804, 'alt': 15.0}, {'lng': -79.949659, 'lat': 40.4135201, 'alt': 15.0}]");
	    taskQueue.add(new TrackingTask(drone, cloudlet, kwargs));
        //taskQueue.add(new TrackingTask(drone, cloudlet, json));
        // Task2/DetectTask START //
        json = "{'gimbal_pitch': -45.0, 'drone_rotation': 0.0, 'sample_rate': 3, 'hover_delay': 10, 'model': 'coco', 'coords': [{'lng': -79.9490267, 'lat': 40.4137749, 'alt': 15.0}, {'lng': -79.9486941, 'lat': 40.4140036, 'alt': 15.0}, {'lng': -79.9493512, 'lat': 40.4140179, 'alt': 15.0}, {'lng': -79.9492386, 'lat': 40.4139199, 'alt': 15.0}, {'lng': -79.9490562, 'lat': 40.413924, 'alt': 15.0}, {'lng': -79.9491152, 'lat': 40.4138075, 'alt': 15.0}, {'lng': -79.9490267, 'lat': 40.4137749, 'alt': 15.0}]}";
        kwargs.clear();
        kwargs.put("gimbal_pitch", "-45.0");
        kwargs.put("drone_rotation", "0.0");
        kwargs.put("sample_rate", "3");
        kwargs.put("hover_delay", "10");
        kwargs.put("model", "coco");
        kwargs.put("coords", "[{'lng': -79.9490267, 'lat': 40.4137749, 'alt': 15.0}, {'lng': -79.9486941, 'lat': 40.4140036, 'alt': 15.0}, {'lng': -79.9493512, 'lat': 40.4140179, 'alt': 15.0}, {'lng': -79.9492386, 'lat': 40.4139199, 'alt': 15.0}, {'lng': -79.9490562, 'lat': 40.413924, 'alt': 15.0}, {'lng': -79.9491152, 'lat': 40.4138075, 'alt': 15.0}, {'lng': -79.9490267, 'lat': 40.4137749, 'alt': 15.0}]");
	    taskQueue.add(new DetectTask(drone, cloudlet, kwargs));
        //taskQueue.add(new DetectTask(drone, cloudlet, json));

	    try {
            drone.connect();
            drone.takeOff();
	        execLoop();
            drone.disconnect();
	    } catch (Exception e) {
            return;
	    }
    }

    @Override
    public void pause() {}
}