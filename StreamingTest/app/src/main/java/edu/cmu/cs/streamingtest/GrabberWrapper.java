package edu.cmu.cs.streamingtest;

import android.util.Log;

//import org.bytedeco.javacv.FFmpegFrameGrabber;
import org.bytedeco.javacv.Frame;
import java.nio.ByteBuffer;

public class GrabberWrapper {
    // Reference to grabber and frame
    private FFmpegFrameGrabber grabber;
    public Frame frame;

    // Resolution settings
    private Integer width;
    private Integer height;

    public GrabberWrapper(FFmpegFrameGrabber _grabber, Integer _width, Integer _height) {
        grabber = _grabber;
        width = _width;
        height = _height;
    }

    public synchronized void grabImageWithSkips(boolean skip, boolean reset) throws Exception {
        grabber.grabWithSkip(skip, reset);
    }

    public synchronized void grabImage() throws Exception {
        frame = grabber.grabImage();
    }

    public synchronized void grabKeyFrame() throws Exception {
        frame = grabber.grabKeyFrame();
        Log.d("GRAB", "Is Keyframe?: " + frame.keyFrame);
    }

    public synchronized Frame getImage() {
        if (frame == null) {
            return null;
        }
        return deepCopyFrame(frame);
    }

    private Frame deepCopyFrame(Frame frame)
    {
        try {
            // Frame that will hold the copy
            Frame cFrame = new Frame(width, height, 8, 3);
            // Copy the byte buffer from frame
            ByteBuffer originalByteBuffer = (ByteBuffer) frame.image[0];
            // Create the clone buffer with same capacity as the original
            ByteBuffer cloneBuffer = ByteBuffer.allocateDirect(originalByteBuffer.capacity());

            // Save parameters from the original byte buffer
            int position = originalByteBuffer.position();
            int limit = originalByteBuffer.limit();

            // Set range to the entire buffer
            originalByteBuffer.position(0).limit(originalByteBuffer.capacity());
            // Read from original and put into clone
            cloneBuffer.put(originalByteBuffer);
            // Set the order same as original
            cloneBuffer.order(originalByteBuffer.order());
            // Set clone position to 0 and set the range as the original
            cloneBuffer.position(0);
            cloneBuffer.position(position).limit(limit);

            // Save the clone
            cFrame.image[0] = cloneBuffer;

            return cFrame;
        } catch (Exception e) {
            return null;
        }
    }

    public synchronized ByteBuffer getImageBuff() throws Exception {
        if (frame == null) {
            return null;
        }
        return deepCopyBuffer(frame);
    }

    private ByteBuffer deepCopyBuffer(Frame frame)
    {
        // Copy the byte buffer from frame
        ByteBuffer originalByteBuffer = (ByteBuffer) frame.image[0];
        // Create the clone buffer with same capacity as the original
        ByteBuffer cloneBuffer = ByteBuffer.allocateDirect(originalByteBuffer.capacity());

        // Save parameters from the original byte buffer
        int position = originalByteBuffer.position();
        int limit = originalByteBuffer.limit();

        // Set range to the entire buffer
        originalByteBuffer.position(0).limit(originalByteBuffer.capacity());
        // Read from original and put into clone
        cloneBuffer.put(originalByteBuffer);
        // Set the order same as original
        cloneBuffer.order(originalByteBuffer.order());
        // Set clone position to 0 and set the range as the original
        cloneBuffer.position(0);
        cloneBuffer.position(position).limit(limit);

        return cloneBuffer;
    }
}
