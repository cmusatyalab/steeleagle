package edu.cmu.cs.dronebrain.interfaces;

import edu.cmu.cs.dronebrain.impl.ParrotAnafi;

public abstract class FlightScript {
    public enum Platform  {ANAFI, DJI}
    public abstract void run();
    public Drone getDrone(Platform p) throws Exception {
        if (p == Platform.ANAFI) {
            return new ParrotAnafi();
        } else {
            throw new Exception("ERROR: Unsupported drone platform specified!");
        }
    }

}
