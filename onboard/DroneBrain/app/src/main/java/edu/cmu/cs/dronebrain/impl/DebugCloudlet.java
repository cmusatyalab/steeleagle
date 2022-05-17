package edu.cmu.cs.dronebrain.impl;

import android.graphics.Bitmap;
import android.util.Log;

import edu.cmu.cs.dronebrain.interfaces.CloudletItf;

public class DebugCloudlet implements CloudletItf {

    String TAG = "DebugCloudlet";

    @Override
    public void sendFrame(Bitmap frame) {
        Log.d(TAG, "Writing frame!");
    }
}
