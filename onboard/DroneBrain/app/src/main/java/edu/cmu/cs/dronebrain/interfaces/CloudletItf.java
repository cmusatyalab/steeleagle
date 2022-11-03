package edu.cmu.cs.dronebrain.interfaces;
import java.util.Vector;

import edu.cmu.cs.gabriel.protocol.Protos;

public interface CloudletItf {
    String ip = "127.0.0.1";
    void processResults(Protos.ResultWrapper resultWrapper);
    void startStreaming(DroneItf drone, String model, Integer sample_rate);
    void stopStreaming();
    void sendFrame(byte[] frame);
    Vector<Double> getDetections(String c);
}
