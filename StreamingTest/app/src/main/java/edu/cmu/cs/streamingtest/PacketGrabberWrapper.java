package edu.cmu.cs.streamingtest;

import static org.bytedeco.ffmpeg.global.avcodec.av_packet_unref;

import android.util.Log;

import org.bytedeco.ffmpeg.avcodec.AVPacket;
import org.bytedeco.ffmpeg.avcodec.AVPacketSideData;
import org.bytedeco.javacv.Frame;

import java.io.DataOutputStream;
import java.nio.ByteBuffer;

public class PacketGrabberWrapper {

    // Reference to grabber and frame
    private FFmpegFrameGrabber grabber;

    // Reference to data output stream
    private DataOutputStream daos;

    public PacketGrabberWrapper(FFmpegFrameGrabber _grabber, DataOutputStream _daos) {
        grabber = _grabber;
        daos = _daos;
    }

    public void grabPacket() throws Exception{
        // Get the packet.
        Long start = System.currentTimeMillis();
        AVPacket packet = grabber.grabPacket();

        // Extract data.
        int dataSize = packet.size();
        ByteBuffer dataBuffer = packet.data().capacity(dataSize).asByteBuffer();
        byte dataBytes[] = new byte[dataSize];
        dataBuffer.get(dataBytes);
        // Write data.
        daos.writeInt(dataSize);
        daos.write(dataBytes);

        //AVPacketSideData sideData = packet.side_data();
        //int sideSize = (int) sideData.size();
        //ByteBuffer sideBuffer = sideData.data().capacity(sideSize).asByteBuffer();
        //byte sideBytes[] = new byte[sideSize];
        //sideBuffer.get(sideBytes);
        // Write side bytes.
        //daos.writeInt(sideSize);
        //daos.write(sideBytes);

        //int sideType = sideData.type();
        //int sideElements = packet.side_data_elems();
        long dts = packet.dts();
        long pts = packet.pts();
        int flags = packet.flags();
        int stream_idx = packet.stream_index();
        // Write extras.
        //daos.writeInt(sideType);
        //daos.writeInt(sideElements);
        daos.writeLong(dts);
        daos.writeLong(pts);
        daos.writeInt(flags);
        daos.writeInt(stream_idx);

        // Send the full packet.
        daos.flush();

        Log.d("GRAB", "Time taken: " + (System.currentTimeMillis() - start));
        Log.d("GRAB", "Sent packet of length " + dataSize);

        // Delete the packets to avoid memory leaks.
        av_packet_unref(packet);
    }
}
