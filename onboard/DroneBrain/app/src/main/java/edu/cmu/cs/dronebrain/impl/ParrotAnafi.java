package edu.cmu.cs.dronebrain.impl;
import android.util.Log;

import edu.cmu.cs.dronebrain.interfaces.Drone;
import edu.cmu.cs.dronebrain.interfaces.Platform;

public class ParrotAnafi implements Drone {
    public void connect() {
        Log.d("FS", "Pretending to connect");
    }

    public void disconnect() {
        Log.d("FS", "Pretending to disconnect");
    }

    public void takeOff() {
        Log.d("FS", "Pretending to takeoff");
    }

    public void land() {
        Log.d("FS", "Pretending to land");
    }

    public void setHome(Double lat, Double lng) {
        Log.d("FS", "Pretending to set home");
    }

    public void moveTo(Double lat, Double lng, Double alt) {
        Log.d("FS", "Pretending to move to");
    }

    public void moveBy(Integer x, Integer y, Integer z) { //x,y,z in meters
        Log.d("FS", "Pretending to move by");
    }

    public void startStreaming(Integer sample_rate) {
        Log.d("FS", "Pretending to start streaming");
    }

    public void rotateBy(Double theta) {
        Log.d("FS", "Pretending to rotate by");
    }

    public void rotateTo(Double theta) {
        Log.d("FS", "Pretending to rotate to");
    }

    public void setGimbalPose(Double yaw_theta, Double pitch_theta, Double roll_theta) {
        Log.d("FS", "Pretending to set gimbal pose");
    }

    public void takePhoto() {
        Log.d("FS", "Pretending to take photo");
    }

    public void getVideoFrame() {
        Log.d("FS", "Pretending to get video frame");
    }
    public void getStatus() {
        Log.d("FS", "Pretending to get status");
    }

    public void cancel() {
        Log.d("FS", "Pretending to cancel");
    }
}
