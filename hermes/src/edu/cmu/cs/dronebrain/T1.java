package edu.cmu.cs.dronebrain;

import edu.cmu.cs.dronebrain.interfaces.DroneItf;
import edu.cmu.cs.dronebrain.interfaces.CloudletItf;
import edu.cmu.cs.dronebrain.interfaces.Task;

public class T1 extends Task {
    
    public T1(DroneItf d, CloudletItf c) {
        super(d, c);
    }

    @Override
    public void run() {
	try {
	    drone.takeOff();
	    drone.moveBy(100.0, 0.0, 0.0);
	} catch (Exception e) {}
    }

    @Override
    public void pause() {}

    @Override
    public void resume() {}
}
