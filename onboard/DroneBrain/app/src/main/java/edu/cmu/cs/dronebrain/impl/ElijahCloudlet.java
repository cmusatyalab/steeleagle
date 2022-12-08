package edu.cmu.cs.dronebrain.impl;

import android.os.Build;
import android.util.Log;

import com.google.protobuf.Any;
import com.google.protobuf.ByteString;
import com.google.protobuf.InvalidProtocolBufferException;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.util.Date;
import java.util.Vector;
import edu.cmu.cs.dronebrain.interfaces.CloudletItf;
import edu.cmu.cs.dronebrain.interfaces.DroneItf;
import edu.cmu.cs.gabriel.client.comm.ServerComm;
import edu.cmu.cs.gabriel.protocol.Protos.InputFrame;
import edu.cmu.cs.gabriel.protocol.Protos.PayloadType;
import edu.cmu.cs.gabriel.protocol.Protos.ResultWrapper;
import edu.cmu.cs.steeleagle.Protos;
import edu.cmu.cs.steeleagle.Protos.Extras;
import java.util.UUID;

public class ElijahCloudlet implements CloudletItf {

    String TAG = "ElijahCloudlet";
    ServerComm comm;
    Thread streamingThread = null;
    String SOURCE = "command"; // Command cognitive engine will handle these image frames
    String detections = null; // JSON string storing the previous seen detections
    String detectionModel = "coco";
    DroneItf drone = null;
    UUID uuid = null;

    Long first_send_frame = null;
    Long first_receive_det = null;

    public ElijahCloudlet(ServerComm s, UUID id) {
        uuid = id;
        comm = s;
    }

    @Override
    public void processResults(Object object) {
        ResultWrapper resultWrapper = (ResultWrapper) object;
        Log.d(TAG, "Results processed by OPENSCOUT with producer: " + resultWrapper.getResultProducerName().getValue());
        if (resultWrapper.getResultsCount() != 1) {
            Log.e(TAG, "Got " + resultWrapper.getResultsCount() + " results in output from OPENSCOUT.");
            return;
        }

        ResultWrapper.Result result = resultWrapper.getResults(0);
        try {
            Extras extras = Extras.parseFrom(resultWrapper.getExtras().getValue());
            ByteString r = result.getPayload();
            Log.i(TAG, r.toString("utf-8"));
            writeDets(r.toString("utf-8"));
            if (first_receive_det == null) {
                JSONArray dets = copyDets();
                if (dets.length() > 0) {
                    Date d = new Date();
                    first_receive_det = d.getTime();
                    Log.d("[TIMING]", "First received detection " + first_receive_det);
                }
            }
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

    private Vector<Double> readDets(String c) throws JSONException {
        JSONArray dets = copyDets();
        if (dets == null)
            return null;
        Log.d(TAG, "Dets: " + dets);

        double conf = 0.0;
        int index = -1;
        for (int i = 0; i < dets.length(); i++) {
            JSONObject jsonobject = dets.getJSONObject(i);
            String cla = jsonobject.getString("class");
            if (cla.equals(c)) { // We found the class we want!
                double classConf = jsonobject.getDouble("score");
                if (classConf > conf) {
                    index = i;
                }
            }
        }

        if (index != -1) {
            JSONObject jsonobject = dets.getJSONObject(index);
            JSONArray bbox = jsonobject.getJSONArray("box");
            Vector<Double> vec = new Vector<Double>();
            vec.add(bbox.getDouble(0));
            vec.add(bbox.getDouble(1));
            vec.add(bbox.getDouble(2));
            vec.add(bbox.getDouble(3));
            return vec;
        } else {
            return null;
        }
    }

    private synchronized JSONArray copyDets() {
        if (detections != null) {
            try {
                JSONArray dets = new JSONArray(detections);
                detections = null; // Invalidate the detection.
                return dets;
            } catch (Exception e) {
                detections = null;
                return null;
            }
        }
        else {
            return null;
        }
    }

    private synchronized void writeDets(String dets) {
        detections = dets;
    }

    @Override
    public void startStreaming(DroneItf d, String model, Integer sample_rate) {
        detectionModel = model;
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
            if (first_send_frame == null) {
                Date d = new Date();
                first_send_frame = d.getTime();
                Log.d("[TIMING]", "First sent frame " + first_send_frame);
            }
            comm.sendSupplier(() -> {
                Extras extras;
                Extras.Builder extrasBuilder = Extras.newBuilder();
                extrasBuilder.setDroneId(uuid.toString());
                extrasBuilder.setDetectionModel(detectionModel);
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
    public Vector<Double> getDetections(String c) {
        try {
            return readDets(c);
        } catch (Exception e) {
            Log.e(TAG, "Got error decoding JSON: " + e.getMessage());
            return null;
        }
    }
}