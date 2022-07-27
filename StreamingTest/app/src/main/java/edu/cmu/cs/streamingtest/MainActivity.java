package edu.cmu.cs.streamingtest;

//import static org.bytedeco.javacpp.avcodec.AV_CODEC_ID_H264;
//import static org.bytedeco.javacpp.avutil.AV_PIX_FMT_YUV420P;
import static org.bytedeco.ffmpeg.global.avcodec.AV_CODEC_ID_H264;
import static org.bytedeco.ffmpeg.global.avcodec.AV_CODEC_ID_RAWVIDEO;
import static org.bytedeco.ffmpeg.global.swscale.SWS_FAST_BILINEAR;
//import static org.bytedeco.javacpp.swscale.SWS_FAST_BILINEAR;

import android.app.Activity;
import android.content.Context;
import android.graphics.Bitmap;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.net.NetworkRequest;
import android.os.Bundle;
import android.os.StrictMode;
import android.util.Log;
import android.view.WindowManager;
import android.widget.ImageView;
import android.widget.TextView;

import org.bytedeco.javacv.AndroidFrameConverter;
import org.bytedeco.javacv.Frame;
//import org.bytedeco.javacv.FFmpegFrameGrabber;

import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.net.Socket;
import java.util.Arrays;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.atomic.AtomicReference;

import javax.net.SocketFactory;

public class MainActivity extends Activity {

    // Private members
    private FFmpegFrameGrabber grabber = null;
    private GrabberWrapper wrapper = null;
    private AndroidFrameConverter converter = null;
    private TextView view = null;
    private ImageView imageView = null;

    private ConnectivityManager connectivityManager = null;
    private Network LTEnetwork = null;
    private Socket socket = null;

    private Integer width = 640;
    private Integer height = 480;

    private String TAG = "StreamingTest";

    Boolean throttle_before_decode = true;
    Integer decodeSkip = 3;
    Integer decodeChunk = 2;

    Boolean throttle = true;
    Integer frameSkip = 10;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        StrictMode.ThreadPolicy policy = new StrictMode.ThreadPolicy.Builder().permitAll().build();
        StrictMode.setThreadPolicy(policy);

        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);

        view = findViewById(R.id.logText);
        imageView = findViewById(R.id.imageView);
        converter = new AndroidFrameConverter();

        grabber = new FFmpegFrameGrabber("rtsp://192.168.42.1/live"); // rtsp url
        //grabber = new FFmpegFrameGrabber("rtsp://wowzaec2demo.streamlock.net/vod/mp4:BigBuckBunny_115k.mp4");
        grabber.setOption("rtsp_transport", "udp");
        //grabber.setOption("skip_frame", "nokey");
        grabber.setOption("buffer_size", "4000000");
        //grabber.setVideoOption("threads", "1");
        //grabber.setVideoOption("preset", "ultrafast");
        grabber.setVideoOption("tune", "fastdecode");

        //grabber.setVideoOption("probesize", "32");
        //grabber.setVideoOption("analyzeduration", "0");
        //grabber.setVideoOption("sync", "ext");
        //grabber.setVideoOption("crf", "30");
        //grabber.setOption("fflags", "nobuffer");
        //grabber.setVideoOption("fps", "1,realtime");
        //grabber.setVideoCodec(AV_CODEC_ID_H264);
        grabber.setImageWidth(width);
        grabber.setImageHeight(height);
        grabber.setImageScalingFlags(SWS_FAST_BILINEAR);

        connectivityManager = (ConnectivityManager) getApplicationContext().getSystemService(Context.CONNECTIVITY_SERVICE);

        CountDownLatch countDownLatch = new CountDownLatch(1);
        NetworkRequest.Builder req = new NetworkRequest.Builder();
        req.addTransportType(NetworkCapabilities.TRANSPORT_CELLULAR);
        connectivityManager.requestNetwork(req.build(), new ConnectivityManager.NetworkCallback() {
                    @Override
                    public void onAvailable(Network network) {
                        LTEnetwork = network;
                        Log.d(TAG, "LTE Connected!");
                        countDownLatch.countDown();
                    }
                }
        );
        try {
            countDownLatch.await();
        } catch (InterruptedException e) {
            e.printStackTrace();
        }


        SocketFactory LTEfactory = LTEnetwork.getSocketFactory();
        try {
            socket = LTEfactory.createSocket("cloudlet040.elijah.cs.cmu.edu", 8485);
            Log.d(TAG, "Opened LTE Socket!");
        } catch (IOException e) {
            Log.d(TAG, "LTE Socket Failed!");
            e.printStackTrace();
        }

        bindProcessToWifi(); // Bind all client sockets to Wifi
    }

    public Network getNetworkObjectForCurrentCellularConnection() {
        List<Network> networks = Arrays.asList(connectivityManager.getAllNetworks());
        for (Network network : networks) {
            NetworkCapabilities capabilities = connectivityManager.getNetworkCapabilities(network);
            if (capabilities.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR)) {
                return network;
            }
        }
        return null;
    }

    public Network getNetworkObjectForCurrentWifiConnection() {
        List<Network> networks = Arrays.asList(connectivityManager.getAllNetworks());
        for (Network network : networks) {
            NetworkCapabilities capabilities = connectivityManager.getNetworkCapabilities(network);
            if (capabilities.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)) {
                return network;
            }
        }
        return null;
    }

    private void bindProcessToWifi() {
        Network network = getNetworkObjectForCurrentWifiConnection();
        if (network != null) {
            Boolean success = connectivityManager.bindProcessToNetwork(network);
            Log.d("WifiConnect", success.toString());
        }
    }

    @Override
    protected void onResume() {
        super.onResume();

        try {
            grabber.start();
            view.setText("Successfully started");
        } catch (FFmpegFrameGrabber.Exception e) {
            Log.d("FFMPEGExc", e.getMessage());
            view.setText(e.getMessage());
        }

        wrapper = new GrabberWrapper(grabber, width, height);

        AtomicReference<Integer> decodeCounter = new AtomicReference<>(0);

        new Thread(() -> {
            while (true) {
                if (decodeCounter.get() % decodeSkip == 0) {
                    decodeCounter.getAndSet(1);
                    // Decode five frames then send.
                    for (int i = 0; i < decodeChunk; ++i) {
                        try {
                            Long start = System.currentTimeMillis();
                            wrapper.grabImage();
                            Log.d("PERF", "Actual grab took: " + (System.currentTimeMillis() - start) + "ms");
                        } catch (Exception e) {
                            e.printStackTrace();
                        }
                    }
                } else {
                    try {
                        Long start = System.currentTimeMillis();
                        wrapper.grabImageWithSkips(true, false);
                        Log.d("PERF", "Skip grab took: " + (System.currentTimeMillis() - start) + "ms");
                    } catch (Exception e) {
                        e.printStackTrace();
                    }
                    decodeCounter.getAndSet(decodeCounter.get() + 1);
                }
                try {
                    Thread.sleep(1);
                } catch (InterruptedException e) {
                    e.printStackTrace();
                }
            }
        }).start();

        new Thread(() -> {
            DataOutputStream daos = null;
            try {
                daos = new DataOutputStream(socket.getOutputStream());
            } catch (IOException e) {
                e.printStackTrace();
            }
            while (true) {
                try {
                    Frame frame = wrapper.getImage();
                    if (frame != null) {
                        Long start = System.currentTimeMillis();
                        ByteArrayOutputStream baos = new ByteArrayOutputStream();

                        Long chk1 = System.currentTimeMillis() - start;

                        start = System.currentTimeMillis();
                        Bitmap bmp = converter.convert(frame);
                        Long chk2 = System.currentTimeMillis() - start;

                        start = System.currentTimeMillis();
                        bmp.compress(Bitmap.CompressFormat.JPEG, 80, baos);
                        Long chk3 = System.currentTimeMillis() - start;

                        start = System.currentTimeMillis();
                        byte[] bytes = baos.toByteArray();
                        Long chk4 = System.currentTimeMillis() - start;

                        start = System.currentTimeMillis();
                        daos.writeInt(bytes.length);
                        daos.write(bytes, 0, bytes.length);
                        Long chk5 = System.currentTimeMillis() - start;

                        start = System.currentTimeMillis();
                        daos.flush();
                        baos.close();
                        Long chk6 = System.currentTimeMillis() - start;

                        Log.d("PERF", "[Checkpoint 1]: " + chk1 + ", [Checkpoint 2]: " + chk2 + ", [Checkpoint 3]: "
                                + chk3 + ", [Checkpoint 4]: " + chk4 + ", [Checkpoint 5]: " + chk5 + ", [Checkpoint 6]: " + chk6);
                    }
                    Thread.sleep(1000);
                } catch (IOException | InterruptedException e) {
                    e.printStackTrace();
                }
            }
        }).start();

        /*
        new Thread(() -> {
            while (true) {
                try {
                    Long start = System.currentTimeMillis();
                    //wrapper.grabImage(false);
                    Log.d("Values", "Counter: " + decodeCounter.get() + ", Skip: " + decodeSkip + ", Bool: " + (decodeCounter.get() % decodeSkip == 0));
                    if (throttle_before_decode && (decodeCounter.get() % decodeSkip != 0)) // Skip frames before decoding.
                    {
                        Log.d("PERF", "Skipping frame");
                        wrapper.grabImageWithSkips(true);
                    } else {
                        wrapper.grabImage();
                    }
                    if (throttle_before_decode)
                        decodeCounter.getAndSet(decodeCounter.get() + 1);
                    //wrapper.grabKeyFrame();
                    Log.d("PERF", "[GRAB IMAGE]: " + (System.currentTimeMillis() - start));
                } catch (Exception e) {
                    Log.d("GrabException", e.getMessage());
                }
                try {
                    Thread.sleep(1);
                } catch (InterruptedException e) {
                    e.printStackTrace();
                }
            }
        }).start();

        new Thread(() -> {
            try {
                //VideoCapture cap = new VideoCapture("rtsp://192.168.42.1/live");
                DataOutputStream daos = new DataOutputStream(socket.getOutputStream());
               // Mat frame = new Mat();
                while (true) {
                    if (throttle && (decodeCounter.get() % frameSkip != 0)) {
                        Log.d("PERF", "Continuing...");
                        continue;
                    }
                    if (wrapper.frame != null)
                    {
                        Long start = System.currentTimeMillis();
                        ByteArrayOutputStream baos = new ByteArrayOutputStream();

                        Long chk1 = System.currentTimeMillis() - start;

                        start = System.currentTimeMillis();
                        Bitmap bmp = converter.convert(wrapper.getImage());
                        Long chk2 = System.currentTimeMillis() - start;

                        start = System.currentTimeMillis();
                        bmp.compress(Bitmap.CompressFormat.JPEG, 80, baos);
                        Long chk3 = System.currentTimeMillis() - start;

                        start = System.currentTimeMillis();
                        byte[] bytes = baos.toByteArray();
                        Long chk4 = System.currentTimeMillis() - start;

                        start = System.currentTimeMillis();
                        daos.writeInt(bytes.length);
                        daos.write(bytes, 0, bytes.length);
                        Long chk5 = System.currentTimeMillis() - start;

                        start = System.currentTimeMillis();
                        daos.flush();
                        baos.close();
                        Long chk6 = System.currentTimeMillis() - start;

                        Log.d("PERF", "[Checkpoint 1]: " + chk1 + ", [Checkpoint 2]: " + chk2 + ", [Checkpoint 3]: "
                                + chk3 + ", [Checkpoint 4]: " + chk4 + ", [Checkpoint 5]: " + chk5 + ", [Checkpoint 6]: " + chk6);
                    }
                    try {
                        Thread.sleep(1000);
                    } catch (InterruptedException e) {
                        e.printStackTrace();
                    }
                }
            } catch (Exception e) {
                Log.d("GrabException", e.getMessage());
            }
        }).start();
        */
        // Testing thread.
        /*
        new Thread(() -> {
            int n = 100000; // Package size in bytes.
            int k = 1000; // Time between sends in ms.
            try {
                DataOutputStream daos = new DataOutputStream(socket.getOutputStream());
                while (true) {
                    daos.writeInt(n);
                    byte[] x = new byte[n];
                    daos.write(x);
                    daos.flush();
                    Log.d("TEST", "Sending " + n + " bytes to server.");

                    try {
                        Thread.sleep(k);
                    } catch (InterruptedException e) {
                        e.printStackTrace();
                    }
                }

            } catch (IOException e) {
                e.printStackTrace();
            }
        }).start();
         */

    }

    @Override
    protected void onStop()
    {
        super.onStop();

        try {
            grabber.stop();
        } catch (FFmpegFrameGrabber.Exception e) {
            Log.d("FFMPEGExc", e.getMessage());
        }
    }

    @Override
    protected void onDestroy()
    {
        super.onDestroy();

        try {
            grabber.release();
            socket.close();
        } catch (FFmpegFrameGrabber.Exception e) {
            Log.d("FFMPEGExc", e.getMessage());
        } catch (IOException e) {
            e.printStackTrace();
        }
    }
}