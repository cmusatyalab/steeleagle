// SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
//
// SPDX-License-Identifier: GPL-2.0-only

package edu.cmu.cs.dronebrain.interfaces;
import java.util.Vector;

public interface CloudletItf {
    String ip = "127.0.0.1";
    void processResults(Object resultWrapper);
    void startStreaming(DroneItf drone, String model, Integer sample_rate);
    void stopStreaming();
    void sendFrame(byte[] frame);
    Vector<Double> getDetections(String c);
}
