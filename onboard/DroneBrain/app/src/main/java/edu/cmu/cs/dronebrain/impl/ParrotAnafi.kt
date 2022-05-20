package edu.cmu.cs.dronebrain.impl

import android.graphics.Bitmap
import android.os.Looper
import android.util.Log
import com.parrot.drone.groundsdk.GroundSdk
import com.parrot.drone.groundsdk.ManagedGroundSdk
import com.parrot.drone.groundsdk.Ref
import com.parrot.drone.groundsdk.device.Drone
import com.parrot.drone.groundsdk.device.instrument.FlyingIndicators
import com.parrot.drone.groundsdk.device.peripheral.MainCamera
import com.parrot.drone.groundsdk.device.peripheral.StreamServer
import com.parrot.drone.groundsdk.device.peripheral.camera.Camera
import com.parrot.drone.groundsdk.device.peripheral.stream.CameraLive
import com.parrot.drone.groundsdk.device.pilotingitf.Activable
import com.parrot.drone.groundsdk.device.pilotingitf.ManualCopterPilotingItf
import com.parrot.drone.groundsdk.device.pilotingitf.GuidedPilotingItf
import com.parrot.drone.groundsdk.facility.AutoConnection
import com.parrot.drone.groundsdk.internal.stream.YUVSink
import com.parrot.drone.groundsdk.stream.GsdkStreamView
import com.parrot.drone.groundsdk.stream.Stream
import com.parrot.drone.groundsdk.value.EnumSetting
import edu.cmu.cs.dronebrain.MainActivity
import edu.cmu.cs.dronebrain.interfaces.DroneItf;
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import java.nio.ByteBuffer
import java.util.concurrent.CountDownLatch

class ParrotAnafi(mainActivity: MainActivity) : DroneItf {

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
    /** Stream sink **/
    private var sink: Stream.Sink? = null
    /** Active frame reference **/
    private var frame: YUVSink.Frame? = null

    /** Callback for the stream **/
    class SinkCallback(p : ParrotAnafi) : YUVSink.Callback {

        /** Logging tag **/
        private var TAG : String = "SinkCallback"
        /** Reference to parent drone **/
        private var parent : ParrotAnafi? = null

        init {
            parent = p
        }

        override fun onStart(sink: YUVSink) {
            // Nothing to do here.
        }

        override fun onFrame(sink: YUVSink, f: YUVSink.Frame) {
            Log.d(TAG, "Received a frame!")
            parent?.setVideoFrame(f)
        }

        override fun onStop(sink: YUVSink) {
            parent?.releaseVideoFrame()
        }
    }

    /** Kill switch for the drone **/
    private var cancel: Boolean = false

    /** Log tag **/
    private var TAG : String = "ParrotAnafi"

    init {
        groundSdk = ManagedGroundSdk.obtainSession(mainActivity)
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

    @Throws(Exception::class)
    override fun connect() {
        Log.d(TAG, "Connect called")
        groundSdk?.resume();
        // Wait until all connections have been established
        val countDownLatch = CountDownLatch(2)
        // Start the AutoConnection process **/
        groundSdk?.getFacility(AutoConnection::class.java) {
            // Called when the auto connection facility is available and when it changes.
            it?.let {
                // Start auto connection.
                if (it.status != AutoConnection.Status.STARTED) {
                    it.start()
                }
                // Set the drone variable and get a reference to the piloting interface. **/
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
                                var sinkCallback = SinkCallback(this)
                                sink = liveStream.openSink(YUVSink.config(Looper.getMainLooper(), sinkCallback))
                            }

                            // Play the live stream.
                            if (liveStream.playState() != CameraLive.PlayState.PLAYING) {
                                liveStream.play()
                            }
                        }
                        // Keep the live stream to know if it is a new one or not.
                        this.liveStream = liveStream
                    }
                }
            } else {
                // Stop monitoring the live stream
                liveStreamRef?.close()
                liveStreamRef = null
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

    /** Helper function for setting current stream frame **/
    fun setVideoFrame(f : YUVSink.Frame) {
        releaseVideoFrame()
        frame = f
    }

    /** Healper function for releasing the current video frame **/
    fun releaseVideoFrame() {
        frame?.release()
        frame = null
    }

    @Throws(Exception::class)
    override fun getVideoFrame(): ByteArray? {
        frame?.nativePtr()
        TODO("This doesn't work yet")
        return null
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
    override fun cancel() {
        Log.d(TAG, "Cancelling previous action...")
        cancel = true
        TODO("Wait for all piloting interfaces to disengage")
        cancel = false
        // Transfer control back to the flight script
    }

    @Throws(Exception::class)
    override fun kill() {
        TODO("Not yet implemented")
    }
}