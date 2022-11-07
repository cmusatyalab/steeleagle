package edu.cmu.cs.dronebrain;

import edu.cmu.cs.dronebrain.interfaces.DroneItf;
import edu.cmu.cs.dronebrain.interfaces.CloudletItf;
import edu.cmu.cs.dronebrain.interfaces.Task;
import java.util.Vector;

public class TrackingTask extends Task {
    
    public TrackingTask(DroneItf d, CloudletItf c) {
        super(d, c);
    }
    
    @Override
    public void run() {
        try {
            String cla = "car";
            System.out.println("About to enter while loop.");
            while (true) {
                Vector<Double> box = cloudlet.getDetections(cla);
                if (box != null) {
                    System.out.println("Got a box!");
                    drone.trackTarget(box, 10.0);
                }
            }            
        } catch (Exception e) {}
    }

    @Override
    public void pause() {}

    @Override
    public void resume() {}
}
