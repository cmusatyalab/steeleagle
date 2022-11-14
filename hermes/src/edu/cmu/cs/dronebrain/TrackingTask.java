package edu.cmu.cs.dronebrain;

import edu.cmu.cs.dronebrain.interfaces.DroneItf;
import edu.cmu.cs.dronebrain.interfaces.CloudletItf;
import edu.cmu.cs.dronebrain.interfaces.Task;
import java.util.Vector;
import java.lang.Thread;

public class TrackingTask extends Task {
    
    public TrackingTask(DroneItf d, CloudletItf c) {
        super(d, c);
    }
    
    @Override
    public void run() {
        try {
            String cla = "person";
            while (true && !Thread.interrupted()) {
                Vector<Double> box = cloudlet.getDetections(cla);
                drone.trackTarget(box, 8.0);
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
