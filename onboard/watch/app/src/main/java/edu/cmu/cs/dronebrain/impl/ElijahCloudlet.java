// SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
//
// SPDX-License-Identifier: GPL-2.0-only

package edu.cmu.cs.dronebrain.impl;

import android.util.Log;

import com.google.protobuf.Any;
import com.google.protobuf.ByteString;
import com.google.protobuf.InvalidProtocolBufferException;

import org.json.JSONArray;

import java.util.Date;
import edu.cmu.cs.dronebrain.interfaces.CloudletItf;
import edu.cmu.cs.dronebrain.interfaces.DroneItf;
import edu.cmu.cs.gabriel.client.comm.ServerComm;
import edu.cmu.cs.gabriel.protocol.Protos.InputFrame;
import edu.cmu.cs.gabriel.protocol.Protos.PayloadType;
import edu.cmu.cs.gabriel.protocol.Protos.ResultWrapper;
import edu.cmu.cs.steeleagle.Protos;
import edu.cmu.cs.steeleagle.Protos.Extras;

import java.util.HashMap;
import java.util.UUID;

public class ElijahCloudlet implements CloudletItf {

    String TAG = "ElijahCloudlet";
    ServerComm comm;
    Thread streamingThread = null;
    String SOURCE = "command"; // Command cognitive engine will handle these image frames
    HashMap<String, String> results = null;
    String model = "coco";
    DroneItf drone = null;
    String uuid = null;

    public ElijahCloudlet(ServerComm s, String id) {
        uuid = id;
        comm = s;
        results = new HashMap<>();
    }

    @Override
    public void processResults(Object object) {
        ResultWrapper resultWrapper = (ResultWrapper) object;
        Log.d(TAG, "Results processed by OPENSCOUT with producer: " + resultWrapper.getResultProducerName().getValue());
        String producer = resultWrapper.getResultProducerName().getValue();
        if (resultWrapper.getResultsCount() != 1) {
            Log.e(TAG, "Got " + resultWrapper.getResultsCount() + " results in output from OPENSCOUT.");
            return;
        }

        ResultWrapper.Result result = resultWrapper.getResults(0);
        try {
            Extras extras = Extras.parseFrom(resultWrapper.getExtras().getValue());
            ByteString r = result.getPayload();
            Log.i(TAG, r.toString("utf-8"));
            writeResults(producer, r.toString("utf-8"));
        } catch (InvalidProtocolBufferException e) {
            Log.e(TAG, "Protobuf Error", e);
        } catch (Exception e) {
            e.printStackTrace();
        }

        if (result.getPayloadType() != PayloadType.TEXT) {
            Log.e(TAG, "Got result of type " + result.getPayloadType().name());
            return;
        }
    }

    private synchronized JSONArray copyResults(String producer) {
        if (results.get(producer) != null) {
            try {
                JSONArray res = new JSONArray(results.get(producer));
                results.put(producer, null); // Invalidate the detection.
                return res;
            } catch (Exception e) {
                results.put(producer, null);
                return null;
            }
        }
        else {
            return null;
        }
    }

    private synchronized void writeResults(String producer, String res) {
        results.put(producer, res);
    }

    private synchronized JSONArray readResults(String producer) { return copyResults(producer); }

    @Override
    public void startStreaming(DroneItf d, String m, Integer sample_rate) {
        model = m;
        if (streamingThread != null) {
            Log.d(TAG, "Cloudlet already streaming, ignoring command");
            return;
        }
        drone = d;
        streamingThread = new Thread(() -> {
            while (true) {
                try {
                    sendFrame(drone.getVideoFrame());
                    Thread.sleep(1000 / sample_rate);
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

    // Based on
    // https://github.com/protocolbuffers/protobuf/blob/master/src/google/protobuf/compiler/java/java_message.cc#L1387
    private static Any pack(Extras engineFields) {
        return Any.newBuilder()
                .setTypeUrl("type.googleapis.com/cnc.Extras")
                .setValue(engineFields.toByteString())
                .build();
    }

    @Override
    public void sendFrame(byte[] frame) {
        if (frame == null)
            return;
        try {
            comm.sendSupplier(() -> {
                Extras extras;
                Extras.Builder extrasBuilder = Extras.newBuilder();
                extrasBuilder.setDroneId(uuid);
                extrasBuilder.setDetectionModel(model);
                Protos.Location.Builder lb = Protos.Location.newBuilder();
                try {
                    lb.setLongitude(drone.getLon());
                    lb.setLatitude(drone.getLat());
                    lb.setAltitude(drone.getAlt());
                } catch (Exception e) {
                    lb.setLongitude(0);
                    lb.setLatitude(0);
                    lb.setAltitude(0);
                }
                extrasBuilder.setLocation(lb);
                extras = extrasBuilder.build();

                return InputFrame.newBuilder()
                        .setPayloadType(PayloadType.IMAGE)
                        .addPayloads(ByteString.copyFrom(frame))
                        .setExtras(pack(extras))
                        .build();
            }, SOURCE, false);
            Log.d(TAG, "Successfully wrote frame to cloudlet!");
        } catch (Exception e) {
            Log.d(TAG, "Failed to write frame to socket, reason: " + e.getMessage());
            e.printStackTrace();
        }
    }

    @Override
    public JSONArray getResults(String producer) {
        return readResults(producer);
    }
}