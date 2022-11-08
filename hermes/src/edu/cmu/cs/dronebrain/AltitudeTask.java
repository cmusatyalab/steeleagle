package edu.cmu.cs.dronebrain;

import edu.cmu.cs.dronebrain.interfaces.DroneItf;
import edu.cmu.cs.dronebrain.interfaces.CloudletItf;
import edu.cmu.cs.dronebrain.interfaces.Task;

public class AltitudeTask extends Task {
    
    double altitude;

    public AltitudeTask(DroneItf d, CloudletItf c, double alt) {
        super(d, c);
        altitude = alt;
    }
    
    @Override
    public void run() {
        try {
            drone.moveBy(0.0, 0.0, -1.0 * altitude);
            drone.setGimbalPose(0.0, -45.0, 0.0);
        } catch (Exception e) {}
    }

    @Override
    public void pause() {}

    @Override
    public void resume() {}
}
