package edu.cmu.cs.dronebrain.impl

import android.app.Activity
import android.util.Log
import com.parrot.drone.groundsdk.ManagedGroundSdk
import com.parrot.drone.groundsdk.Ref
import com.parrot.drone.groundsdk.device.Drone
import com.parrot.drone.groundsdk.device.pilotingitf.ManualCopterPilotingItf
import com.parrot.drone.groundsdk.facility.AutoConnection
import edu.cmu.cs.dronebrain.MainActivity
import edu.cmu.cs.dronebrain.interfaces.DroneItf;

class ParrotAnafi(mainActivity: MainActivity) : DroneItf {

    /* Variable for storing GroundSDK object **/
    private var groundSdk : ManagedGroundSdk? = null
    /* Variable for storing the drone object **/
    private var drone : Drone? = null
    /* Variable for storing piloting interface **/
    private var pilotingItfRef: Ref<ManualCopterPilotingItf>? = null

    /* Log tag **/
    private var TAG : String = "ParrotAnafi"

    init {
        groundSdk = ManagedGroundSdk.obtainSession(mainActivity)
    }

    @Throws(Exception::class)
    override fun connect() {
        /* Start the AutoConnection process **/
        groundSdk!!.getFacility(AutoConnection::class.java) {
            // Called when the auto connection facility is available and when it changes.
            it?.let {
                /* Start auto connection. **/
                if (it.status != AutoConnection.Status.STARTED) {
                    it.start()
                }
                /* Set the drone variable **/
                drone = it.drone
                pilotingItfRef = drone?.getPilotingItf(ManualCopterPilotingItf::class.java) {}
                Log.d(TAG, "Connected to drone")
            }
        }
    }

    @Throws(Exception::class)
    override fun disconnect() {
        Log.d(TAG, "Disconnected")
    }

    @Throws(Exception::class)
    override fun takeOff() {
        pilotingItfRef?.get()?.let { itf ->
            /* Do the action according to the interface capabilities **/
            if (itf.canTakeOff()) {
                /* Take off **/
                itf.takeOff()
            }
        }
    }

    @Throws(Exception::class)
    override fun land() {
        pilotingItfRef?.get()?.let { itf ->
            /* Do the action according to the interface capabilities **/
            if (itf.canLand()) {
                /* Land **/
                itf.land()
            }
        }
    }

    @Throws(Exception::class)
    override fun setHome(lat: Double?, lng: Double?) {

    }

    @Throws(Exception::class)
    override fun moveTo(lat: Double?, lng: Double?, alt: Double?) {

    }

    @Throws(Exception::class)
    override fun moveBy(x: Int?, y: Int?, z: Int?) { //x,y,z in meters

    }

    @Throws(Exception::class)
    override fun startStreaming(sample_rate: Int?) {

    }

    @Throws(Exception::class)
    override fun rotateBy(theta: Double?) {

    }

    @Throws(Exception::class)
    override fun rotateTo(theta: Double?) {

    }

    @Throws(Exception::class)
    override fun setGimbalPose(yaw_theta: Double?, pitch_theta: Double?, roll_theta: Double?) {

    }

    @Throws(Exception::class)
    override fun takePhoto() {

    }

    @Throws(Exception::class)
    override fun getVideoFrame() {

    }

    @Throws(Exception::class)
    override fun getStatus() {

    }

    @Throws(Exception::class)
    override fun cancel() {

    }
}