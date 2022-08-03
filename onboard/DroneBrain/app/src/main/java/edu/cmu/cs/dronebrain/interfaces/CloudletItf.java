package edu.cmu.cs.dronebrain.interfaces;

public interface CloudletItf {
    String ip = "127.0.0.1";

    void startStreaming(DroneItf drone);

    void stopStreaming();

    void sendFrame(byte[] frame);
}
