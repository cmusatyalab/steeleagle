package edu.cmu.cs.dronebrain.interfaces;


public interface Drone {
    void connect(FlightScript.Platform p);
    void disconnect();
    void takeOff();
    void land();
    void setHome(Double lat, Double lng);
    void moveTo(Double lat, Double lng, Double alt);
    void moveBy(Integer x, Integer y, Integer z); //x,y,z in meters

}
