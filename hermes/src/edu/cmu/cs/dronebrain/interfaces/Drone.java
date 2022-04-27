package edu.cmu.cs.dronebrain.interfaces;

public interface Drone {
    void connect(String ip);
    void disconnect();
    void takeOff();
    void land();
    void setHome(Double lat, Double lng);
    void moveTo(Double lat, Double lng, Double alt);
    void moveBy(Integer x, Integer y, Integer z); //x,y,z in meters
    void startStreaming(Integer sample_rate);
    void rotateBy(Double theta);
    void rotateTo(Double theta);
    void setGimbalPose(Double yaw_theta, Double pitch_theta, Double roll_theta);
    void takePhoto();
    void getVideoFrame();
    void getStatus();
    void cancel();
}

