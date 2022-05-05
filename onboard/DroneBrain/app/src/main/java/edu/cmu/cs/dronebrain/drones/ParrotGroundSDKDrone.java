package edu.cmu.cs.dronebrain.drones;

import android.app.Activity;

import com.parrot.drone.groundsdk.GroundSdk;
import com.parrot.drone.groundsdk.ManagedGroundSdk;

import edu.cmu.cs.dronebrain.interfaces.DroneItf;

public class ParrotGroundSDKDrone implements DroneItf {

    private Activity parent = null;
    private GroundSdk groundSdk = null;

    public ParrotGroundSDKDrone(Activity activity) {
        parent = activity;
    }

    public void connect() { groundSdk = ManagedGroundSdk.obtainSession(parent); }

    public void takeoff() {

    }
}
