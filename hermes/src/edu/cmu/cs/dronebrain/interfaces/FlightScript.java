package edu.cmu.cs.dronebrain.interfaces;

public abstract class FlightScript {
    public Platform platform;
    public abstract void run(Drone drone, Cloudlet cloudlet);
}
