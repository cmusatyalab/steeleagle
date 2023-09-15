// SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
//
// SPDX-License-Identifier: GPL-2.0-only

package edu.cmu.cs.dronebrain;

import edu.cmu.cs.dronebrain.interfaces.DroneItf;
import edu.cmu.cs.dronebrain.interfaces.CloudletItf;
import edu.cmu.cs.dronebrain.interfaces.Task;
import java.lang.Float;
import java.util.HashMap;
import org.json.JSONArray;
import org.json.JSONObject;
import android.util.Log;

public class DetectTask extends Task {
    
    Double gimbal;
    public DetectTask(DroneItf d, CloudletItf c, HashMap<String, String> k) {
        super(d, c, k);
	gimbal = Double.parseDouble(kwargs.get("gimbal_pitch"));
    }
    
    @Override
    public void run() {
        try {
            drone.setGimbalPose(0.0, gimbal, 0.0);
	    cloudlet.switchModel("coco");
	    Log.d("DetectTask", "Parsing coordinates...");
	    JSONArray coords = new JSONArray(kwargs.get("coords"));
	    for (int i = 0; i < coords.length(); i++) {
		Log.d("DetectTask", "Moving to coordinate " + i);
		JSONObject coord = coords.getJSONObject(i);
		double lat = coord.getDouble("lat");
		double lng = coord.getDouble("lng");
		double alt = coord.getDouble("alt");
		drone.moveTo(lat, lng, alt);
	    }
        } catch (Exception e) {
	    Log.e("DetectTask", e.toString());
	}
    }

    @Override
    public void pause() {}

    @Override
    public void resume() {}
}
