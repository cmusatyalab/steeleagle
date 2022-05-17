package edu.cmu.cs.dronebrain.interfaces;

import android.graphics.Bitmap;

public interface CloudletItf {
    String ip = "127.0.0.1";

    void sendFrame(Bitmap frame);
}
