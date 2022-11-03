package edu.cmu.cs.dronebrain;

import edu.cmu.cs.dronebrain.interfaces.DroneItf;
import edu.cmu.cs.dronebrain.interfaces.CloudletItf;
import edu.cmu.cs.dronebrain.interfaces.Task;
import java.lang.InterruptedException;

public class T2 extends Task {

    public T2(DroneItf d, CloudletItf c) {
        super(d, c);
    }

    @Override
    public void run() {
        try {
            System.out.println("T2.run()");
            drone.moveBy(0.0, 100.0, 0.0);
        } catch (Exception e) {
            return;
        }

    }

    @Override
    public void pause() {
        try {
            System.out.println("T2.pause()");
        } catch (Exception e) {

        }
    }

    @Override
    public void resume() {
    }
}
