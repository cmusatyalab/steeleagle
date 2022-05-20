package edu.cmu.cs.dronebrain.interfaces;

import org.w3c.dom.ranges.DocumentRange;

public abstract class FlightScript {
    public Platform platform;
    protected DroneItf drone;
    protected CloudletItf cloudlet;
    public abstract void run();
}
