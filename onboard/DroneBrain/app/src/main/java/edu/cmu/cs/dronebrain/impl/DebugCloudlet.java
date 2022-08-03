package edu.cmu.cs.dronebrain.impl;

import android.graphics.Bitmap;
import android.util.Log;

import edu.cmu.cs.dronebrain.interfaces.CloudletItf;
import edu.cmu.cs.dronebrain.interfaces.DroneItf;

public class DebugCloudlet implements CloudletItf {

    String TAG = "DebugCloudlet";

    @Override
    public void startStreaming(DroneItf drone) {
        Log.d(TAG, "Streaming frames from drone.");
    }

    @Override
    public void stopStreaming() {
        Log.d(TAG, "Stopping frame stream from drone.");
    }

    @Override
    public void sendFrame(byte[] frame) {
        Log.d(TAG, "Writing frame!");
    }
}
