// SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
//
// SPDX-License-Identifier: GPL-2.0-only

package edu.cmu.cs.dronebrain;

import edu.cmu.cs.dronebrain.interfaces.DroneItf;
import edu.cmu.cs.dronebrain.interfaces.CloudletItf;
import edu.cmu.cs.dronebrain.interfaces.Task;
import java.lang.Float;
import java.util.HashMap;

public class DetectTask extends Task {
    
    double altitude;
    public DetectTask(DroneItf d, CloudletItf c, HashMap<String, String> k) {
        super(d, c, k);
        altitude = new Float(kwargs.get("altitude"));

    }
    
    @Override
    public void run() {
        try {
            drone.setGimbalPose(0.0, -30.0, 0.0);
            drone.moveBy(0.0, 0.0, -1.0 * altitude);
        } catch (Exception e) {}
    }

    @Override
    public void pause() {}

    @Override
    public void resume() {}
}
