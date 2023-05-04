// SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
//
// SPDX-License-Identifier: GPL-2.0-only

package edu.cmu.cs.dronebrain.interfaces;

import java.util.ArrayList;
import java.util.Vector;

public interface DroneItf {
    void init() throws Exception;
    void connect() throws Exception;
    void disconnect() throws Exception;
    void takeOff() throws Exception;
    void land() throws Exception;
    void setHome(Double lat, Double lng) throws Exception;
    void moveTo(Double lat, Double lng, Double alt) throws Exception;
    void moveBy(Double x, Double y, Double z) throws Exception; //x,y,z in meters
    void startStreaming(Integer resolution) throws Exception;
    byte[] getVideoFrame() throws Exception;
    void stopStreaming() throws Exception;
    void rotateBy(Double theta) throws Exception;
    void rotateTo(Double theta) throws Exception;
    void setGimbalPose(Double yaw_theta, Double pitch_theta, Double roll_theta) throws Exception;
    void takePhoto() throws Exception;
    void PCMD(Integer pitch, Integer yaw, Integer roll);
    // TODO: Remove this, it's for testing only.
    ArrayList<Double> calculateOffsets(Integer pixel_x, Integer pixel_y, Double leash);
    void trackTarget(Vector<Double> box, Double leash) throws Exception;
    void lookAtTarget(Vector<Double> box) throws Exception;
    void getStatus() throws Exception;
    String getName() throws Exception;
    Double getLat() throws Exception;
    Double getLon() throws Exception;
    Double getAlt() throws Exception;
    Double getExactAlt() throws Exception;
    Double getHeading() throws Exception;
    void hover() throws Exception;
    void cancel() throws Exception;
    void kill() throws Exception;
}


