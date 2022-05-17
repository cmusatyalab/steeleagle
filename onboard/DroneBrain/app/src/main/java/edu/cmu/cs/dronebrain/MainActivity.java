package edu.cmu.cs.dronebrain;

import android.app.Activity;
import android.content.Context;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.net.NetworkRequest;
import android.os.Bundle;
import android.os.StrictMode;
import android.util.Log;
import android.view.WindowManager;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.concurrent.CountDownLatch;

import dalvik.system.DexClassLoader;
import edu.cmu.cs.dronebrain.impl.DebugCloudlet;
import edu.cmu.cs.dronebrain.impl.ParrotAnafi;
import edu.cmu.cs.dronebrain.interfaces.CloudletItf;
import edu.cmu.cs.dronebrain.interfaces.DroneItf;
import edu.cmu.cs.dronebrain.interfaces.FlightScript;
import edu.cmu.cs.dronebrain.interfaces.Platform;


public class MainActivity extends Activity {

    /** LTE network object **/
    private Network LTEnetwork = null;
    /** Currently executing FlightScript **/
    private FlightScript MS = null;
    /** Current drone object **/
    private DroneItf drone = null;
    /** Current cloudlet object **/
    private CloudletItf cloudlet = null;

    /** Log tag **/
    String TAG = "DroneBrain";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        StrictMode.ThreadPolicy policy = new StrictMode.ThreadPolicy.Builder().permitAll().build();
        StrictMode.setThreadPolicy(policy);

        CountDownLatch countDownLatch = new CountDownLatch(1);
        /** Create LTE network binding **/
        ConnectivityManager cm = (ConnectivityManager) getApplicationContext().getSystemService(Context.CONNECTIVITY_SERVICE);
        NetworkRequest.Builder req = new NetworkRequest.Builder();
        req.addTransportType(NetworkCapabilities.TRANSPORT_CELLULAR);
        cm.requestNetwork(req.build(), new ConnectivityManager.NetworkCallback() {
                    @Override
                    public void onAvailable(Network network) {
                        /** Assign LTE network object **/
                        LTEnetwork = network;
                        countDownLatch.countDown();
                    }
                }
        );
        try {
            countDownLatch.await();
        } catch (InterruptedException e) {
            e.printStackTrace();
        }
    }

    @Override
    protected void onStart(){
        super.onStart();

        /** Download flight plan **/
        File f = new File(getDir("dex", MODE_PRIVATE), "classes.dex");
        try {
            Log.d(TAG, "Starting flight plan download");
            download("http://cloudlet040.elijah.cs.cmu.edu/classes.dex", f);
            /** Read data from flight plan **/
            DexClassLoader classLoader = new DexClassLoader(
                    f.getAbsolutePath(), getDir("outdex", MODE_PRIVATE).getAbsolutePath(),
                    null, getClassLoader());
            Class clazz = classLoader.loadClass("edu.cmu.cs.dronebrain.MS");
            Log.i(TAG, clazz.toString());
            MS = (FlightScript)clazz.newInstance();
            drone = getDrone(MS.platform); // Get the corresponding drone
            cloudlet = getCloudlet(); // Get the corresponding cloudlet
        } catch (Exception e) {
            Log.e(TAG, "Download failed! " + e.toString());
        }
    }

    @Override
    protected void onResume() {
        super.onResume();

        try {
            /** Execute flight plan **/
            Log.d(TAG, "Executing flight plan!");
            new Thread(new Runnable() {
                @Override
                public void run() {
                    MS.run(drone, cloudlet);
                }
            }).start();
        } catch (Exception e) {
            Log.e(TAG, e.toString());
        }
    }

    private DroneItf getDrone(Platform platform) throws Exception {
        if (platform == Platform.ANAFI) {
            return new ParrotAnafi(this);
        } else {
            throw new Exception("Unsupported platform: " + platform.name());
        }
    }

    private CloudletItf getCloudlet() {
        return new DebugCloudlet();
    }

    /** This needs to change in future to pull from CNC module **/
    private void download(String url, File dex) throws Exception {
        BufferedInputStream bis;
        BufferedOutputStream bos;
        try {
            URL urlObject = new URL(url);
            HttpURLConnection httpConn = (HttpURLConnection) LTEnetwork.openConnection(urlObject);
            int responseCode = httpConn.getResponseCode();
            if (responseCode != HttpURLConnection.HTTP_OK) {
                throw new RuntimeException("Download didn't work, http status: " + responseCode);
            }
            bis = new BufferedInputStream(httpConn.getInputStream());
            bos = new BufferedOutputStream(new FileOutputStream(dex));
            copy(bis, bos);
            bis.close();
            bos.close();
        } catch (IOException e) {
            throw new IOException(e);
        }
    }

    /** Helper function used by download **/
    private void copy(BufferedInputStream src, OutputStream dst) throws IOException {
        int len;
        byte[] buf = new byte[8 * 1024];
        while ((len = src.read(buf, 0, 8 * 1024)) > 0) {
            dst.write(buf, 0, len);
        }
    }
}
