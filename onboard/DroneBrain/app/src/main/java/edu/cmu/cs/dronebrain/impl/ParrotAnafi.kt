package edu.cmu.cs.dronebrain.impl

import android.util.Log
import com.parrot.drone.groundsdk.GroundSdk
import com.parrot.drone.groundsdk.Ref
import com.parrot.drone.groundsdk.device.Drone
import com.parrot.drone.groundsdk.device.instrument.FlyingIndicators
import com.parrot.drone.groundsdk.device.pilotingitf.Activable
import com.parrot.drone.groundsdk.device.pilotingitf.ManualCopterPilotingItf
import com.parrot.drone.groundsdk.device.pilotingitf.GuidedPilotingItf
import com.parrot.drone.groundsdk.facility.AutoConnection
import edu.cmu.cs.dronebrain.MainActivity
import edu.cmu.cs.dronebrain.interfaces.DroneItf;
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import java.util.concurrent.CountDownLatch

class ParrotAnafi(mainActivity: MainActivity) : DroneItf {

    /** Variable for storing GroundSDK object **/
    private var groundSdk : GroundSdk? = null
    /** Variable for storing the drone object **/
    private var drone : Drone? = null
    /** Variable for storing piloting interface **/
    private var pilotingItfRef: Ref<ManualCopterPilotingItf>? = null
    /** Variable for storing guidance interface **/
    private var guidedPilotingItf: Ref<GuidedPilotingItf>? = null
    /** Variable for storing flying indicators **/
    private var flyingIndicatorsRef: Ref<FlyingIndicators>? = null

    /** Kill switch for the drone **/
    private var kill: Boolean = false

    /** Log tag **/
    private var TAG : String = "ParrotAnafi"

    init {
        groundSdk = GroundSdk.newSession(mainActivity.applicationContext, null);
    }

    suspend fun wait_to_complete_manual_flight() {
        Log.d(TAG, "Waiting for task to complete")
        while (flyingIndicatorsRef?.get()?.flyingState != FlyingIndicators.FlyingState.WAITING
            && !kill) {
            delay(1)
        }
    }

    suspend fun wait_to_complete_guided_flight() {
        Log.d(TAG, "Waiting for guided task to complete")
        while (guidedPilotingItf?.get()?.state != Activable.State.IDLE && !kill) {
            delay(1)
        }
    }

    @Throws(Exception::class)
    override fun connect() {
        Log.d(TAG, "Connect called")
        groundSdk?.resume();
        /** Wait until all connections have been established **/
        val countDownLatch = CountDownLatch(2)
        /** Start the AutoConnection process **/
        groundSdk?.getFacility(AutoConnection::class.java) {
            // Called when the auto connection facility is available and when it changes.
            it?.let {
                /** Start auto connection. **/
                if (it.status != AutoConnection.Status.STARTED) {
                    it.start()
                }
                /** Set the drone variable and get a reference to the piloting interface. **/
                drone = it.drone
                pilotingItfRef = drone?.getPilotingItf(ManualCopterPilotingItf::class.java) {
                    it?.let {
                        when (it.state) {
                            Activable.State.UNAVAILABLE -> {
                                // Piloting interface is unavailable.
                            }
                            Activable.State.IDLE -> {
                                if (guidedPilotingItf?.get()?.state != Activable.State.ACTIVE)
                                    it.activate()
                            }
                            Activable.State.ACTIVE -> {
                                when {
                                    it.canTakeOff() -> {
                                        countDownLatch.countDown()
                                    }
                                    it.canLand() -> {
                                        countDownLatch.countDown()
                                    }
                                }
                            }
                        }
                    }
                }
                flyingIndicatorsRef = drone?.getInstrument(FlyingIndicators::class.java) {
                    countDownLatch.countDown()
                }
            }
        }
        countDownLatch.await()
        Log.d(TAG, "Got to end of connect.")
    }

    @Throws(Exception::class)
    override fun disconnect() {
        Log.d(TAG, "Disconnecting from drone")
        groundSdk?.disconnectDrone(drone!!.uid)
    }

    @Throws(Exception::class)
    override fun takeOff() {
        Log.d(TAG, "Takeoff called")
        pilotingItfRef?.get()?.let { itf ->
            /** Do the action according to the interface capabilities **/
            if (itf.canTakeOff()) {
                /** Take off **/
                itf.takeOff()
            }
        }
        runBlocking {
            wait_to_complete_manual_flight()
        }

        var countDownLatch = CountDownLatch(1)
        /** Get the guided piloting interface **/
        guidedPilotingItf = drone?.getPilotingItf(GuidedPilotingItf::class.java) {
            it?.let {
                when (it.state) {
                    Activable.State.UNAVAILABLE -> {
                        // Piloting interface is unavailable.
                    }
                    Activable.State.IDLE -> {
                        // Piloting interface is idle.
                        countDownLatch.countDown()
                    }
                    Activable.State.ACTIVE -> {
                        Log.d(TAG, "Guided interface is available.")
                        countDownLatch.countDown()
                    }
                }
            }
        }
        countDownLatch.await()
        Log.d(TAG, "Finished takeoff process")
    }

    @Throws(Exception::class)
    override fun land() {
        Log.d(TAG, "Landing called")
        pilotingItfRef?.get()?.let { itf ->
            /** Do the action according to the interface capabilities **/
            if (itf.canLand()) {
                /** Land **/
                itf.land()
            }
        }
    }

    @Throws(Exception::class)
    override fun setHome(lat: Double?, lng: Double?) {

    }

    @Throws(Exception::class)
    override fun moveTo(lat: Double, lng: Double, alt: Double) {
        var directive = GuidedPilotingItf.LocationDirective(lat, lng, alt, GuidedPilotingItf.LocationDirective.Orientation.TO_TARGET, null)
        Log.d(TAG, "$lat $lng $alt")

        guidedPilotingItf?.get()?.let {
            it.move(directive)
        }

        /** Wait to complete the flight **/
        runBlocking {
            wait_to_complete_guided_flight()
        }
    }

    @Throws(Exception::class)
    override fun moveBy(x: Double, y: Double, z: Double) { //x,y,z in meters
        var directive = GuidedPilotingItf.RelativeMoveDirective(x, y, z, 0.0, null)

        guidedPilotingItf?.get()?.let {
            it.move(directive)
        }

        runBlocking {
            wait_to_complete_guided_flight()
        }
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

    @Throws(Exception::class)
    override fun kill() {
        TODO("Not yet implemented")
    }
}