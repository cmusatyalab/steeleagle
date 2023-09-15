// SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
//
// SPDX-License-Identifier: GPL-2.0-only

package edu.cmu.cs.dronebrain.impl;

import android.util.Log;

import org.json.JSONArray;

import java.util.Vector;

import edu.cmu.cs.dronebrain.interfaces.CloudletItf;
import edu.cmu.cs.dronebrain.interfaces.DroneItf;

public class DebugCloudlet implements CloudletItf {

    String TAG = "DebugCloudlet";

    @Override
    public void processResults(Object resultWrapper) {}

    @Override
    public void startStreaming(DroneItf drone, String model, Integer sample_rate) {
        Log.d(TAG, "Streaming frames from drone.");
    }

    @Override
    public void stopStreaming() {
        Log.d(TAG, "Stopping frame stream from drone.");
    }

    @Override
    public void switchModel(String model) { Log.d(TAG, "Switching model!"); }

    @Override
    public void sendFrame(byte[] frame) {
        Log.d(TAG, "Writing frame!");
    }

    @Override
    public JSONArray getResults(String key) {return new JSONArray();}
}
