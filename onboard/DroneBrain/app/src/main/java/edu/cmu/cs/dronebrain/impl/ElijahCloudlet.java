package edu.cmu.cs.dronebrain.impl;

import android.net.Network;
import android.util.Log;

import java.io.DataOutputStream;
import java.io.IOException;
import java.net.Socket;

import javax.net.SocketFactory;

import edu.cmu.cs.dronebrain.interfaces.CloudletItf;
import edu.cmu.cs.dronebrain.interfaces.DroneItf;

public class ElijahCloudlet implements CloudletItf {

    String TAG = "ElijahCloudlet";
    Socket sock = null;
    DataOutputStream daos = null;
    Thread streamingThread = null;

    public ElijahCloudlet(Network net) {
        SocketFactory factory = net.getSocketFactory();
        try {
            sock = factory.createSocket("cloudlet040.elijah.cs.cmu.edu", 8485);
            Log.d(TAG, "Opened socket to cloudlet.");
        } catch (IOException e) {
            Log.d(TAG, "Connection to cloudlet failed, reason: " + e.getMessage());
            e.printStackTrace();
        }
        try {
            daos = new DataOutputStream(sock.getOutputStream());
        } catch (IOException e) {
            Log.d(TAG, "Failed to get output stream from socket, reason: " + e.getMessage());
            e.printStackTrace();
        }
    }

    @Override
    public void startStreaming(DroneItf drone) {
        streamingThread = new Thread(() -> {
            while (true) {
                try {
                    sendFrame(drone.getVideoFrame());
                    Thread.sleep(1000);
                } catch (Exception e) {
                    Log.d(TAG, "Send frame failed, reason: " + e.getMessage());
                    e.printStackTrace();
                }
            }
        });
        streamingThread.start();
    }

    @Override
    public void stopStreaming() {
        streamingThread.interrupt();
    }

    @Override
    public void sendFrame(byte[] frame) {
        try {
            daos.writeInt(frame.length);
            daos.write(frame);
            daos.flush();
            Log.d(TAG, "Successfully wrote frame to cloudlet!");
        } catch (IOException e) {
            Log.d(TAG, "Failed to write frame to socket, reason: " + e.getMessage());
            e.printStackTrace();
        }
    }
}