// SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
//
// SPDX-License-Identifier: GPL-2.0-only

package edu.cmu.cs.dronebrain;

import edu.cmu.cs.dronebrain.interfaces.DroneItf;
import edu.cmu.cs.dronebrain.interfaces.CloudletItf;
import edu.cmu.cs.dronebrain.interfaces.Task;
import java.lang.Float;
import java.util.*;
import java.lang.System;
import org.apache.commons.lang3.tuple.ImmutablePair;
import org.json.JSONArray;
import org.json.JSONObject;
import javax.vecmath.Vector2d;


public class ObstacleTask extends Task {
    
    float altitude;
    int speed;
    String model;
    ImmutablePair<Double, Double> start;
    ImmutablePair<Double, Double> end;
    public ObstacleTask(DroneItf d, CloudletItf c, HashMap<String, String> k) {
        super(d, c, k);
        try {
            altitude = Float.parseFloat(kwargs.get("altitude"));
            speed = Integer.parseInt(kwargs.get("speed"));
            model = kwargs.get("model");
            JSONArray coords = new JSONArray(kwargs.get("coords"));
            JSONObject first = coords.getJSONObject(0);
            start = new ImmutablePair<>(first.getDouble("lat"), first.getDouble("lng"));
            JSONObject second = coords.getJSONObject(1);
            end = new ImmutablePair<>(second.getDouble("lat"), second.getDouble("lng"));
        } catch (Exception e) {
            System.out.println("[FLIGHTSCRIPT]: " + e.toString());
        }
    }
    
    private double getHeading(ImmutablePair<Double, Double> a, ImmutablePair<Double, Double> b) {
        double aTheta = Math.toRadians(a.getKey());
        double aL = Math.toRadians(a.getValue());
        double bTheta = Math.toRadians(b.getKey());
        double bL = Math.toRadians(b.getValue());
        
        double X = Math.cos(bTheta) * Math.sin(bL - aL);
        double Y = (Math.cos(aTheta) * Math.sin(bTheta)) - (Math.sin(aTheta) * Math.cos(bTheta) * Math.cos(bL - aL));
        return Math.toDegrees(Math.atan2(X, Y));
    }

    private boolean reachedDestination() {
        try {
            Vector2d currentPos = new Vector2d(drone.getLat(), drone.getLon());
            Vector2d startPos = new Vector2d(start.getKey(), start.getValue());
            Vector2d endPos = new Vector2d(end.getKey(), end.getValue());
            
            currentPos.sub(startPos);
            endPos.sub(startPos);
            System.out.println("DIST CURR: " + Double.toString(currentPos.length()));
            System.out.println("DIST GOAL: " + Double.toString(endPos.length()));
            
            double diff = currentPos.dot(endPos) - endPos.lengthSquared();
            System.out.println("DIST DOT: " + Double.toString(diff));
            
            return diff > 0.0;
        } catch (Exception e) {
            System.out.println("Exception occured: " + e.toString());
            return false;
        }
    }

    private void moveForwardAndAvoid() {
        int lastoffset = 0;
        while (!reachedDestination() && !exit) {
            try {
                JSONArray res = cloudlet.getResults("obstacle-avoidance");
                int offset = 0;
                if (res != null) {
                    JSONObject obj = res.getJSONObject(0);
                    offset = obj.getInt("vector");
                    System.out.println("Offset vector: " + Integer.toString(offset));
                    // Hysteresis
                    int diff = (int)((offset - lastoffset));
                    float ratio = (offset + diff) / 640;
                    int move = (int)((ratio * 100));
                    drone.PCMD(speed, 0, offset);
                    lastoffset = offset;
                } else {
                    drone.PCMD(speed, 0, lastoffset);
                }
                Thread.sleep(50);
            } catch (Exception e) {
                return;
            }
            lastoffset = (int)(lastoffset / 1.2);
        } 
        drone.PCMD(0, 0, 0);
    }

    @Override
    public void run() {
        try {
            drone.startStreaming(480);
            cloudlet.startStreaming(drone, model, 1);
            drone.setGimbalPose(0.0, 0.0, 0.0);
            System.out.println("[FLIGHTSCRIPT]: Got before MoveTo");
            drone.moveTo(start.getKey(), start.getValue(), 2.0);
            System.out.println("[FLIGHTSCRIPT]: Finished MoveTo, getting heading");
            double headingTarget = getHeading(start, end);
            drone.rotateTo(headingTarget);
            System.out.println("[FLIGHTSCRIPT]: Rotating to face heading");
            double currentAltitude = drone.getExactAlt();
            System.out.println("[FLIGHTSCRIPT]: Descending to altitude");
            //drone.moveBy(0.0, 0.0, altitude - currentAltitude);
            System.out.println("[FLIGHTSCRIPT]: Avoiding");
            moveForwardAndAvoid();
            System.out.println("[FLIGHTSCRIPT]: Reached destination");
        } catch (Exception e) {
            System.out.println("[FLIGHTSCRIPT]: " + e.toString());
        }
    }

    @Override
    public void pause() {}

    @Override
    public void resume() {}
}
