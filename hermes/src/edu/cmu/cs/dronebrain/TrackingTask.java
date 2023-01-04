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

public class TrackingTask extends Task {
    
    public TrackingTask(DroneItf d, CloudletItf c) {
        super(d, c);
    }
    
    @Override
    public void run() {
        try {
            String cla = "robomaster";
            //Vector<Double> box = cloudlet.getDetections(cla);
            //while (box == null) {
            //    box = cloudlet.getDetections(cla);
            //}
            //drone.trackTarget(box, 20.0);
            //Thread.sleep(50);
            //while (true) {
            //    drone.trackTarget(null, 20.0);
            //    box = cloudlet.getDetections(cla);
            //    if (box != null) {
            //        int pixel_x = (int)Math.round((((box.get(3) - box.get(1)) / 2.0) + box.get(1)) * 640);
            //        int pixel_y = (int)Math.round((1 - (((box.get(2) - box.get(0)) / 2.0) + box.get(0))) * 480);
            //        drone.calculateOffsets(pixel_x, pixel_y, 20.0);
            //    }
            //    Thread.sleep(50);
            //}
            while (true && !Thread.interrupted()) {
                Vector<Double> box = cloudlet.getDetections(cla);
                //drone.trackTarget(box, 17.0);
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
