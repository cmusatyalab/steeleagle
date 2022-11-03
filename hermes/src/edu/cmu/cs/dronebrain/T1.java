package edu.cmu.cs.dronebrain;

import edu.cmu.cs.dronebrain.interfaces.DroneItf;
import edu.cmu.cs.dronebrain.interfaces.CloudletItf;
import edu.cmu.cs.dronebrain.interfaces.Task;
import java.lang.InterruptedException;

public class T1 extends Task {

    public T1(DroneItf d, CloudletItf c) {
        super(d, c);
    }

    @Override
    public void run() {
        try {
            System.out.println("T1.run()");
            drone.moveBy(100.0, 0.0, 0.0);
        } catch (Exception e) {
            return;
        }

    }

    @Override
    public void pause() {
        try {
            System.out.println("T1.pause()");
        } catch (Exception e) {

        }
    }

    @Override
    public void resume() {
    }
}
