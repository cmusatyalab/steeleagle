// SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
//
// SPDX-License-Identifier: GPL-2.0-only

package edu.cmu.cs.dronebrain;

import edu.cmu.cs.dronebrain.interfaces.DroneItf;
import edu.cmu.cs.dronebrain.interfaces.CloudletItf;
import edu.cmu.cs.dronebrain.interfaces.Task;
import java.util.Vector;
import java.lang.Thread;
import java.lang.Math;
import java.util.HashMap;

import org.json.JSONArray;
import org.json.JSONObject;
import org.json.JSONException;

import org.apache.commons.math3.geometry.euclidean.threed.Vector3D;
import org.apache.commons.math3.geometry.euclidean.threed.Rotation;
import org.apache.commons.math3.geometry.euclidean.threed.RotationConvention;
import org.apache.commons.math3.geometry.euclidean.threed.RotationOrder;

public class TrackingTask extends Task {
    
    public TrackingTask(DroneItf d, CloudletItf c, HashMap<String, String> kwargs) {
        super(d, c, kwargs);
    }
    
    public Vector3D getMovementVectors(Double yaw, Double pitch, Double leash) {
        Vector3D forward_vec = new Vector3D(0.0, 1.0, 0.0);
        Rotation rotation = new Rotation(RotationOrder.ZYX, RotationConvention.VECTOR_OPERATOR, yaw * (Math.PI / 180.0), 0.0, (pitch + -30) * (Math.PI / 180.0));
        Vector3D target_direction = rotation.applyTo(forward_vec);
        Vector3D target_vector = new Vector3D(0.0,0.0,15);

        Vector3D leash_vec = null;
        if (target_vector.getNorm() > 0.0)
            leash_vec = target_vector.normalize().scalarMultiply(leash);
        else
            leash_vec = target_vector;
        Vector3D movement_vector = target_vector.subtract(leash_vec);

        return movement_vector;
    }

    private Vector<Double> getDetectionForClass(String c) {
	JSONArray dets = cloudlet.getResults("openscout-object");
	if (dets == null)
            return null;

        double conf = 0.0;
        int index = -1;
        for (int i = 0; i < dets.length(); i++) {
	    try {
                JSONObject jsonobject = dets.getJSONObject(i);
            	String cla = jsonobject.getString("class");
            	if (cla.equals(c)) { // We found the class we want!
            	    double classConf = jsonobject.getDouble("score");
            	    if (classConf > conf) {
            	        index = i;
            	    }
            	}
	    } catch (JSONException e) {}
        }

        if (index != -1) {
	    try {
            	JSONObject jsonobject = dets.getJSONObject(index);
            	JSONArray bbox = jsonobject.getJSONArray("box");
            	Vector<Double> vec = new Vector<Double>();
		System.out.println("[TRACK]: BBOX found");
            	vec.add(bbox.getDouble(0));
            	vec.add(bbox.getDouble(1));
            	vec.add(bbox.getDouble(2));
                vec.add(bbox.getDouble(3));
            	return vec;
	    } catch (JSONException e) { return null; }
        } else {
            return null;
        }
    }

    @Override
    public void run() {
        try {
	    drone.startStreaming(480);
	    cloudlet.startStreaming(drone, "coco", 1);
	    drone.setGimbalPose(0.0, 0.0, 0.0);
	    String cla = "person";
	    System.out.println("[TRACK]: About to start tracking loop!");
            while (true && !Thread.interrupted()) {
		Vector<Double> box = getDetectionForClass(cla);
		drone.lookAtTarget(box);
                Thread.sleep(50); 
            }            
        } catch (Exception e) {
            return;
        }
    }

    @Override
    public void pause() {}

    @Override
    public void resume() {}
}
