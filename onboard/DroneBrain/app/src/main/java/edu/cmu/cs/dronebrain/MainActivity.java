package edu.cmu.cs.dronebrain;

import android.app.Activity;
import android.content.Context;
import android.location.Location;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.net.NetworkRequest;
import android.net.wifi.WifiManager;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.StrictMode;
import android.util.Log;
import android.view.WindowManager;
import android.webkit.URLUtil;

import com.google.protobuf.Any;
import com.google.protobuf.ByteString;
import com.google.protobuf.InvalidProtocolBufferException;
import com.parrot.drone.groundsdk.ManagedGroundSdk;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.DatagramSocket;
import java.net.HttpURLConnection;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.SocketAddress;
import java.net.SocketException;
import java.net.URL;
import java.util.Arrays;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.function.Consumer;

import javax.net.SocketFactory;

import dalvik.system.DexClassLoader;
import edu.cmu.cs.dronebrain.impl.DebugCloudlet;
import edu.cmu.cs.dronebrain.impl.parrotanafi.ParrotAnafi;
import edu.cmu.cs.dronebrain.interfaces.CloudletItf;
import edu.cmu.cs.dronebrain.interfaces.DroneItf;
import edu.cmu.cs.dronebrain.interfaces.FlightScript;
import edu.cmu.cs.dronebrain.interfaces.Platform;
import edu.cmu.cs.gabriel.client.comm.ServerComm;
import edu.cmu.cs.gabriel.client.results.ErrorType;
import edu.cmu.cs.gabriel.protocol.Protos.InputFrame;
import edu.cmu.cs.gabriel.protocol.Protos.ResultWrapper;
import edu.cmu.cs.gabriel.protocol.Protos.PayloadType;
import edu.cmu.cs.steeleagle.Protos;
import edu.cmu.cs.steeleagle.Protos.Extras;


public class MainActivity extends Activity implements Consumer<ResultWrapper> {
    private ManagedGroundSdk sdk = null;
    /** Connectivity Manager to retrieve network infos **/
    private ConnectivityManager cm = null;
    /** LTE network object **/
    private Network LTEnetwork = null;
    /** Currently executing FlightScript **/
    private FlightScript MS = null;
    /** Reference to the thread executing the FlightScript **/
    private Thread scriptRunnable = null;
    /** Current drone object **/
    private DroneItf drone = null;
    /** Current cloudlet object **/
    private CloudletItf cloudlet = null;
    /** For Gabriel client connection **/
    private ServerComm serverComm = null;
    /** Script URL send from commander **/
    private String scriptUrl = null;
    private Handler loopHandler = null;
    private int heartbeatsSent = 0;
    /** Log tag **/
    String TAG = "DroneBrain";
    String SOURCE = "command";


    // Based on
    // https://github.com/protocolbuffers/protobuf/blob/master/src/google/protobuf/compiler/java/java_message.cc#L1387
    private static Any pack(Extras engineFields) {
        return Any.newBuilder()
                .setTypeUrl("type.googleapis.com/cnc.Extras")
                .setValue(engineFields.toByteString())
                .build();
    }

    public String getWifiSSID() {
        WifiManager wm = (WifiManager) this.getApplicationContext().getSystemService(Context.WIFI_SERVICE);
        if(wm != null) {
            return wm.getConnectionInfo().getSSID();
        } else {
            return "";
        }
    }

    @Override
    public void accept(ResultWrapper resultWrapper) {
        if (resultWrapper.getResultsCount() != 1) {
            Log.e(TAG, "Got " + resultWrapper.getResultsCount() + " results in output.");
            return;
        }

        ResultWrapper.Result result = resultWrapper.getResults(0);
        try {
            Extras extras = Extras.parseFrom(resultWrapper.getExtras().getValue());
            ByteString r = result.getPayload();
            if(extras.hasCmd()) {
                Protos.Command cmd = extras.getCmd();
                if(cmd.getHalt()) {
                    Log.i(TAG, "Killswitch signaled from commander.");
                    if (scriptRunnable != null) {
                        scriptRunnable.interrupt();
                        Log.i(TAG, "Interrupting script thread.");
                    }
                    if (drone != null) {
                        Log.i(TAG, "Killing drone.");
                        drone.kill();
                    }
                    finish();
                }

                if(URLUtil.isValidUrl(cmd.getScriptUrl())) {
                    Log.i(TAG, "Flight script sent by commander.");
                    scriptUrl = cmd.getScriptUrl();
                    Log.i(TAG, scriptUrl);
                    if(retrieveFlightScript())
                        executeFlightScript();
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
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        StrictMode.ThreadPolicy policy = new StrictMode.ThreadPolicy.Builder().permitAll().build();
        StrictMode.setThreadPolicy(policy);

        sdk = ManagedGroundSdk.obtainSession(this);

        CountDownLatch countDownLatch = new CountDownLatch(1);
        /** Create LTE network binding **/
        cm = (ConnectivityManager) getApplicationContext().getSystemService(Context.CONNECTIVITY_SERVICE);
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

        Consumer<ErrorType> onDisconnect = errorType -> {
            Log.e(TAG, "Disconnect Error:" + errorType.name());
            finish();
        };

        serverComm = ServerComm.createServerComm(
                this, BuildConfig.GABRIEL_HOST, BuildConfig.PORT, getApplication(), onDisconnect);

        loopHandler = new Handler();
        loopHandler.postDelayed(gabrielLoop, 1000);

        /** Bind all future sockets to Wifi **/
        //bindProcessToWifi();
    }

    public Network getNetworkObjectForCurrentWifiConnection() {
        List<Network> networks = Arrays.asList(cm.getAllNetworks());
        for (Network network : networks) {
            NetworkCapabilities capabilities = cm.getNetworkCapabilities(network);
            if (capabilities.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)) {
                return network;
            }
        }
        return null;
    }

    private void bindProcessToWifi() {
        Network network = getNetworkObjectForCurrentWifiConnection();
        if (network != null) {
            Boolean success = cm.bindProcessToNetwork(network);
            Log.d("WifiConnect", success.toString());
        }
    }

    private Runnable gabrielLoop = new Runnable() {

        @Override
        public void run() {
            heartbeatsSent++;
            serverComm.sendSupplier(() -> {
                String p = "heartbeat";

                Extras extras;
                Extras.Builder extrasBuilder = Extras.newBuilder();
                Protos.Location.Builder lb = Protos.Location.newBuilder();
                Location l = null;
                try {
                    if(drone != null) {
                        lb.setLatitude(drone.getLat());
                        lb.setLongitude(drone.getLon());
                        extrasBuilder.setLocation(lb);
                    } else {
                        lb.setLatitude(0);
                        lb.setLongitude(0);
                        extrasBuilder.setLocation(lb);
                    }

                    extrasBuilder.setDroneId(Build.ID);

                    if(heartbeatsSent < 2) {
                        extrasBuilder.setRegistering(true);
                    }
                } catch (Exception e) {
                    e.printStackTrace();
                }
                extras = extrasBuilder.build();

                return InputFrame.newBuilder()
                        .setPayloadType(PayloadType.TEXT)
                        .addPayloads(ByteString.copyFromUtf8(p))
                        .setExtras(pack(extras))
                        .build();
            }, SOURCE, false);
            loopHandler.postDelayed(this, 1000);
        }
    };

    protected boolean retrieveFlightScript() {
        boolean success = false;
        /** Download flight plan **/
        File f = new File(getDir("dex", MODE_PRIVATE), "classes.dex");
        try {
            Log.d(TAG, "Starting flight plan download");
            download(scriptUrl, f);
            /** Read data from flight plan **/
            DexClassLoader classLoader = new DexClassLoader(
                    f.getAbsolutePath(), getDir("outdex", MODE_PRIVATE).getAbsolutePath(),
                    null, getClassLoader());
            Class clazz = classLoader.loadClass("edu.cmu.cs.dronebrain.MS");
            Log.i(TAG, clazz.toString());
            MS = (FlightScript)clazz.newInstance();
            Log.d(TAG, "Getting drone and cloudlet...");
            drone = getDrone(MS.platform); // Get the corresponding drone
            cloudlet = getCloudlet(); // Get the corresponding cloudlet
            success = true;
        } catch (Exception e) {
            Log.e(TAG, "Download failed! " + e.toString());
        }
        return success;
    }

    protected void executeFlightScript() {
        try {
            /** Execute flight plan **/
            Log.d(TAG, "Executing flight plan!");
            MS.setDrone(drone);
            MS.setCloudlet(cloudlet);
            scriptRunnable = new Thread(new Runnable() {
                @Override
                public void run() {
                    MS.run();
                }
            });
            scriptRunnable.start();
        } catch (Exception e) {
            Log.e(TAG, e.toString());
        }
    }

    @Override
    protected void onStart(){
        super.onStart();


    }

    @Override
    protected void onResume() {
        super.onResume();
        heartbeatsSent = 0;
    }

    private DroneItf getDrone(Platform platform) throws Exception {
        if (platform == Platform.ANAFI) {
            return new ParrotAnafi(sdk);
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

    @Override
    protected void onDestroy() {
        super.onDestroy();
        sdk.close();
    }
}
