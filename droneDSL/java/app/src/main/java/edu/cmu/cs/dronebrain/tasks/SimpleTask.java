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
import org.json.JSONObject;
import android.util.Log;


public class SimpleTask extends Task {
    
    public SimpleTask(DroneItf d, CloudletItf c, HashMap<String, String> kwargs) {
        super(d, c, kwargs);
        Log.d("SimpleTask", "Instantiating SimpleTask...");
    }
    
    @Override
    public void run() {
        try {
            JSONObject json = new JSONObject("{'x': 5.0, 'y': 5.0, 'z': -15.0}");
            drone.setGimbalPose(0.0, -30.0, 0.0);
            drone.moveBy(json.getDouble("x"), json.getDouble("y"), json.getDouble("z"));
        } catch (Exception e) {
            Log.d("SimpleTask", e.toString());
        }
    }

    @Override
    public void pause() {}

    @Override
    public void resume() {}
}
