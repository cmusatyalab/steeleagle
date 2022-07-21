package edu.cmu.cs.streamingtest;

//import static org.bytedeco.javacpp.avcodec.AV_CODEC_ID_H264;
//import static org.bytedeco.javacpp.avcodec.AV_CODEC_ID_RAWVIDEO;
//import static org.bytedeco.javacpp.avutil.AV_PIX_FMT_YUV420P;
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
//import org.bytedeco.javacv.FFmpegFrameGrabber;
import org.bytedeco.javacv.Frame;
import org.opencv.core.Mat;
import org.opencv.videoio.VideoCapture;

import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.net.Socket;
import java.nio.ByteBuffer;
import java.util.Arrays;
import java.util.List;
import java.util.concurrent.CountDownLatch;

import javax.net.SocketFactory;

public class MainActivity extends Activity {

    // Private members
    private FFmpegFrameGrabber grabber = null;
    private PacketGrabberWrapper wrapper = null;
    private AndroidFrameConverter converter = null;
    private TextView view = null;
    private ImageView imageView = null;

    private ConnectivityManager connectivityManager = null;
    private Network LTEnetwork = null;
    private Socket socket = null;

    private Integer width = 640;
    private Integer height = 480;

    private String TAG = "StreamingTest";


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
        //grabber.setVideoOption("fps", "1,realtime");
        //grabber.setVideoCodec(AV_CODEC_ID_RAWVIDEO);
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

        // Thread for reading and grabbing packets then sending them over the network.
        new Thread(() -> {
            try {
                DataOutputStream daos = new DataOutputStream(socket.getOutputStream());
                wrapper = new PacketGrabberWrapper(grabber, daos);
                while (true) {
                    wrapper.grabPacket();
                }
            } catch (Exception e) {
                Log.d("GrabException", e.getMessage());
            }
        }).start();
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