package edu.cmu.cs.dronebrain.interfaces;

public interface DroneItf {
    void connect() throws Exception;
    void disconnect() throws Exception;
    void takeOff() throws Exception;
    void land() throws Exception;
    void setHome(Double lat, Double lng) throws Exception;
    void moveTo(Double lat, Double lng, Double alt) throws Exception;
    void moveBy(Double x, Double y, Double z) throws Exception; //x,y,z in meters
    void startStreaming(Integer sample_rate) throws Exception;
    void rotateBy(Double theta) throws Exception;
    void rotateTo(Double theta) throws Exception;
    void setGimbalPose(Double yaw_theta, Double pitch_theta, Double roll_theta) throws Exception;
    void takePhoto() throws Exception;
    void getVideoFrame() throws Exception;
    void getStatus() throws Exception;
    void cancel() throws Exception;
}


