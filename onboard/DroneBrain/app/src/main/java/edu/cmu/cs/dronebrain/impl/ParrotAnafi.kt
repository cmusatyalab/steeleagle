package edu.cmu.cs.dronebrain.impl

import android.graphics.Bitmap
import android.location.Location
import android.util.Log
import com.parrot.drone.groundsdk.GroundSdk
import com.parrot.drone.groundsdk.ManagedGroundSdk
import com.parrot.drone.groundsdk.Ref
import com.parrot.drone.groundsdk.device.Drone
import com.parrot.drone.groundsdk.device.instrument.FlyingIndicators
import com.parrot.drone.groundsdk.device.instrument.Gps
import com.parrot.drone.groundsdk.device.peripheral.Copilot
import com.parrot.drone.groundsdk.device.peripheral.MainCamera
import com.parrot.drone.groundsdk.device.peripheral.StreamServer
import com.parrot.drone.groundsdk.device.peripheral.camera.Camera
import com.parrot.drone.groundsdk.device.peripheral.stream.CameraLive
import com.parrot.drone.groundsdk.device.pilotingitf.Activable
import com.parrot.drone.groundsdk.device.pilotingitf.ManualCopterPilotingItf
import com.parrot.drone.groundsdk.device.pilotingitf.GuidedPilotingItf
import com.parrot.drone.groundsdk.facility.AutoConnection
import com.parrot.drone.groundsdk.stream.GsdkStreamView
import com.parrot.drone.groundsdk.value.EnumSetting
import edu.cmu.cs.dronebrain.MainActivity
import edu.cmu.cs.dronebrain.interfaces.DroneItf;
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import java.nio.ByteBuffer
import java.util.concurrent.CountDownLatch

class ParrotAnafi(sdk: ManagedGroundSdk) : DroneItf {

    /** Variable for storing GroundSDK object **/
    private var groundSdk : ManagedGroundSdk? = null
    /** Variable for storing the drone object **/
    private var drone : Drone? = null

    /** Variable for storing piloting interface **/
    private var pilotingItfRef: Ref<ManualCopterPilotingItf>? = null
    /** Variable for storing guidance interface **/
    private var guidedPilotingItf: Ref<GuidedPilotingItf>? = null
    /** Variable for storing flying indicators **/
    private var flyingIndicatorsRef: Ref<FlyingIndicators>? = null

    /** Reference to the current drone stream server Peripheral. **/
    private var streamServerRef: Ref<StreamServer>? = null
    /** Reference to the current drone live stream. **/
    private var liveStreamRef: Ref<CameraLive>? = null
    /** Current drone live stream. **/
    private var liveStream: CameraLive? = null
    /** Video stream view. **/
    private lateinit var streamView: GsdkStreamView

    /** Kill switch for the drone **/
    private var cancel: Boolean = false

    /** Log tag **/
    private var TAG : String = "ParrotAnafi"

    init {
        groundSdk = sdk
    }

    suspend fun wait_to_complete_manual_flight() {
        Log.d(TAG, "Waiting for task to complete")
        while (flyingIndicatorsRef?.get()?.flyingState != FlyingIndicators.FlyingState.WAITING
            && !cancel) {
            delay(1)
        }
    }

    suspend fun wait_to_complete_guided_flight() {
        Log.d(TAG, "Waiting for guided task to complete")
        while (guidedPilotingItf?.get()?.state != Activable.State.IDLE && !cancel) {
            delay(1)
        }
    }

    override fun init() {

    }

    @Throws(Exception::class)
    override fun connect() {
        Log.d(TAG, "Connect called")
        groundSdk?.resume();
        // Wait until all connections have been established
        val countDownLatch = CountDownLatch(2)
        // Start the AutoConnection process
        groundSdk?.getFacility(AutoConnection::class.java) {
            // Called when the auto connection facility is available and when it changes.
            it?.let {
                // Start auto connection.
                if (it.status != AutoConnection.Status.STARTED) {
                    it.start()
                }
                // Set the drone variable and get a reference to the piloting interface.
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
            // Do the action according to the interface capabilities
            if (itf.canTakeOff()) {
                // Take off
                itf.takeOff()
            }
        }
        runBlocking {
            wait_to_complete_manual_flight()
        }

        var countDownLatch = CountDownLatch(1)
        // Get the guided piloting interface
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
            // Do the action according to the interface capabilities
            if (itf.canLand()) {
                // Land
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
        // Monitor the stream server.
        streamServerRef = drone?.getPeripheral(StreamServer::class.java) { streamServer ->
            // Called when the stream server is available and when it changes.

            if (streamServer != null) {
                // Enable Streaming
                if(!streamServer.streamingEnabled()) {
                    streamServer.enableStreaming(true)
                }

                // Monitor the live stream.
                if (liveStreamRef == null) {
                    liveStreamRef = streamServer.live { liveStream ->
                        // Called when the live stream is available and when it changes.

                        if (liveStream != null) {
                            if (this.liveStream == null) {
                                // It is a new live stream.

                                // Set the live stream as the stream
                                // to be render by the stream view.
                                streamView.setStream(liveStream)
                            }

                            // Play the live stream.
                            if (liveStream.playState() != CameraLive.PlayState.PLAYING) {
                                liveStream.play()
                            }
                        } else {
                            // Stop rendering the stream
                            streamView.setStream(null)
                        }
                        // Keep the live stream to know if it is a new one or not.
                        this.liveStream = liveStream
                    }
                }
            } else {
                // Stop monitoring the live stream
                liveStreamRef?.close()
                liveStreamRef = null
                // Stop rendering the stream
                streamView.setStream(null)
            }
        }
    }

    @Throws(Exception::class)
    override fun stopStreaming() {
        // Cleanup livestream resources
        liveStreamRef?.close()
        liveStreamRef = null

        streamServerRef?.close()
        streamServerRef = null

        liveStream = null
    }

    /** Helper function for transforming Bitmap to byte array **/
    fun Bitmap.convertToByteArray(): ByteArray = ByteBuffer.allocate(byteCount).apply {
        copyPixelsToBuffer(this)
        rewind()
    }.array()

    @Throws(Exception::class)
    override fun getVideoFrame(): ByteArray? {
        var frame: Bitmap? = null
        var countDownLatch = CountDownLatch(1)
        streamView?.capture {
            frame = it
            countDownLatch.countDown()
        }
        countDownLatch.await()
        return frame?.convertToByteArray()
    }

    @Throws(Exception::class)
    override fun rotateBy(theta: Double) {
        var directive = GuidedPilotingItf.RelativeMoveDirective(0.0, 0.0, 0.0, theta, null)

        guidedPilotingItf?.get()?.let {
            it.move(directive)
        }

        runBlocking {
            wait_to_complete_guided_flight()
        }
    }

    @Throws(Exception::class)
    override fun rotateTo(theta: Double?) {

    }

    @Throws(Exception::class)
    override fun setGimbalPose(yaw_theta: Double?, pitch_theta: Double?, roll_theta: Double?) {

    }

    @Throws(Exception::class)
    override fun takePhoto() {
        var countDownLatch = CountDownLatch(1)
        drone?.getPeripheral(MainCamera::class.java) {
            it?.mode()?.value = Camera.Mode.PHOTO
            if (it?.canStartPhotoCapture() == true) {
                it?.startPhotoCapture()
            }
            countDownLatch.countDown()
        }
        countDownLatch.await()
    }

    @Throws(Exception::class)
    override fun getStatus() {

    }

    @Throws(Exception::class)
    override fun getName(): String? {
        var name : String = "Unnamed"
        if (drone?.name != null)
            name = drone!!.name
        return name
    }

    override fun getLat(): Double? {
        var lat : Double = 0.0
        drone?.getInstrument(Gps::class.java) {
            if (it?.lastKnownLocation()?.latitude != null) {
                lat = it.lastKnownLocation()!!.latitude
            }
        }
        return lat
    }

    override fun getLon(): Double? {
        var lon : Double = 0.0
        drone?.getInstrument(Gps::class.java) {
            if (it?.lastKnownLocation()?.longitude != null) {
                lon = it.lastKnownLocation()!!.longitude
            }
        }
        return lon
    }

    override fun getAlt(): Double? {
        var alt : Double = 0.0
        drone?.getInstrument(Gps::class.java) {
            if (it?.lastKnownLocation()?.altitude != null) {
                alt = it?.lastKnownLocation()!!.altitude
            }
        }
        return alt
    }

    @Throws(Exception::class)
    override fun cancel() {
        Log.d(TAG, "Cancelling previous action...")
        cancel = true
        TODO("Wait for all piloting interfaces to disengage")
        cancel = false
        // Transfer control back to the flight script
    }

    @Throws(Exception::class)
    override fun kill() {
        pilotingItfRef?.get()?.let { itf ->
            itf.hover()
        }
        drone?.getPeripheral(Copilot::class.java)?.source()?.value = Copilot.Source.REMOTE_CONTROL
        groundSdk?.disconnectDrone(drone!!.uid)
    }
}