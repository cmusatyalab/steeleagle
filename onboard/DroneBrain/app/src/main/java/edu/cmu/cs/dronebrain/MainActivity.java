package edu.cmu.cs.dronebrain;

import android.app.Activity;
import android.content.Context;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.net.NetworkRequest;
import android.os.Bundle;
import android.util.Log;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.MalformedURLException;
import java.net.URL;

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

    /** Log tag **/
    String TAG = "DroneBrain";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        /** Create LTE network binding **/
        ConnectivityManager cm = (ConnectivityManager) getApplicationContext().getSystemService(Context.CONNECTIVITY_SERVICE);
        NetworkRequest.Builder req = new NetworkRequest.Builder();
        req.addTransportType(NetworkCapabilities.TRANSPORT_CELLULAR);
        cm.requestNetwork(req.build(), new ConnectivityManager.NetworkCallback() {
                    @Override
                    public void onAvailable(Network network) {
                        /** Assign LTE network object **/
                        LTEnetwork = network;
                    }
                }
        );
    }

    @Override
    protected void onStart(){
        super.onStart();

        /** Download flight plan **/
        File f = new File(getDir("dex", MODE_PRIVATE), "classes.dex");
        try {
            download("http://cloudlet040.elijah.cs.cmu.edu/classes.dex", f);
            /** Read data from flight plan **/
            DexClassLoader classLoader = new DexClassLoader(
                    f.getAbsolutePath(), getDir("outdex", MODE_PRIVATE).getAbsolutePath(),
                    null, getClassLoader());

            try {
                Class clazz = classLoader.loadClass("edu.cmu.cs.dronebrain.MS");
                Log.i(TAG, clazz.toString());
                FlightScript inst = (FlightScript)clazz.newInstance();
                Log.i(TAG, inst.toString());
                /** Execute flight plan **/
                DroneItf drone = getDrone(inst.platform); // Get the corresponding drone
                CloudletItf cloudlet = getCloudlet(); // Get the corresponding cloudlet
                inst.run(drone, cloudlet);
            } catch (Exception e) {
                Log.e(TAG, e.toString());
            }
        } catch (Exception e) {
            Log.e(TAG, "Download failed!");
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
            HttpURLConnection httpConn = (HttpURLConnection) urlObject.openConnection();
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
