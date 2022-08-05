package edu.cmu.cs.dronebrain.impl;

import android.location.Location;
import android.os.Build;
import android.util.Log;

import com.google.protobuf.Any;
import com.google.protobuf.ByteString;
import com.google.protobuf.InvalidProtocolBufferException;

import java.io.IOException;
import java.util.function.Consumer;

import edu.cmu.cs.dronebrain.interfaces.CloudletItf;
import edu.cmu.cs.dronebrain.interfaces.DroneItf;
import edu.cmu.cs.gabriel.client.comm.ServerComm;
import edu.cmu.cs.gabriel.protocol.Protos;
import edu.cmu.cs.steeleagle.Protos.Extras;

public class ElijahCloudlet implements CloudletItf, Consumer<Protos.ResultWrapper> {

    String TAG = "ElijahCloudlet";
    ServerComm comm = null;
    Thread streamingThread = null;
    String SOURCE = "openscout"; //openscout cognitive engine will handle these image frames

    public ElijahCloudlet(ServerComm s) {
        comm = s;
    }

    @Override
    public void accept(Protos.ResultWrapper resultWrapper) {
        if (resultWrapper.getResultsCount() != 1) {
            Log.e(TAG, "Got " + resultWrapper.getResultsCount() + " results in output.");
            return;
        }

        Protos.ResultWrapper.Result result = resultWrapper.getResults(0);
        try {
            Extras extras = Extras.parseFrom(resultWrapper.getExtras().getValue());
            ByteString r = result.getPayload();
            Log.i(TAG, r.toString());
        } catch (InvalidProtocolBufferException e) {
            Log.e(TAG, "Protobuf Error", e);
        } catch (Exception e) {
            e.printStackTrace();
        }

        if (result.getPayloadType() != Protos.PayloadType.TEXT) {
            Log.e(TAG, "Got result of type " + result.getPayloadType().name());
            return;
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
        try {
            comm.sendSupplier(() -> {
                Extras extras;
                Extras.Builder extrasBuilder = Extras.newBuilder();
                extrasBuilder.setDroneId(Build.ID);
                extras = extrasBuilder.build();

                return Protos.InputFrame.newBuilder()
                        .setPayloadType(Protos.PayloadType.IMAGE)
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
}