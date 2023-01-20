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
       // Vector3D target_vector = find_intersection(target_direction, new Vector3D(0.0, 0.0, 15));
        Vector3D target_vector = new Vector3D(0.0,0.0,15);

        Vector3D leash_vec = null;
        if (target_vector.getNorm() > 0.0)
            leash_vec = target_vector.normalize().scalarMultiply(leash);
        else
            leash_vec = target_vector;
        Vector3D movement_vector = target_vector.subtract(leash_vec);

        return movement_vector;
    }

    @Override
    public void run() {
        try {
            String cla = kwargs.get("class");
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
