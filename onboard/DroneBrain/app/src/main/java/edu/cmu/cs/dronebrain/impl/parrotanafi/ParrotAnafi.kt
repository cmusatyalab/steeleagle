package edu.cmu.cs.dronebrain.impl.parrotanafi

import android.graphics.Bitmap
import android.net.Network
import android.util.Log
import com.parrot.drone.groundsdk.ManagedGroundSdk
import com.parrot.drone.groundsdk.Ref
import com.parrot.drone.groundsdk.device.Drone
import com.parrot.drone.groundsdk.device.instrument.FlyingIndicators
import com.parrot.drone.groundsdk.device.instrument.Gps
import com.parrot.drone.groundsdk.device.peripheral.MainCamera
import com.parrot.drone.groundsdk.device.peripheral.camera.Camera
import com.parrot.drone.groundsdk.device.pilotingitf.Activable
import com.parrot.drone.groundsdk.device.pilotingitf.GuidedPilotingItf
import com.parrot.drone.groundsdk.device.pilotingitf.ManualCopterPilotingItf
import com.parrot.drone.groundsdk.facility.AutoConnection
import edu.cmu.cs.dronebrain.interfaces.DroneItf
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import org.bytedeco.ffmpeg.global.swscale
import org.bytedeco.javacv.AndroidFrameConverter
import org.bytedeco.javacv.Frame
import java.io.ByteArrayOutputStream
import java.io.InputStream
import java.net.Socket
import java.util.concurrent.CountDownLatch
import javax.net.SocketFactory

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

    /** Stores a reference to the FFMPEG video stream reader **/
    private var grabber: FFmpegFrameGrabber? = null
    /** Wraps calls to the frame grabber **/
    private var wrapper: GrabberWrapper? = null
    /** Determines how many frames to skip and how many to decode to keep up
     *  with slow decode speeds on the Android Watch. These settings are specific
     *  to the Samsung Galaxy Watch 4. You may find that your device performs better
     *  with different settings.
     */
    private var skip: Int = 3
    private var decode: Int = 2
    private var thread: Thread? = null
    /** Converter that transforms AVFrames into Bitmaps **/
    private var converter = AndroidFrameConverter()
    /** Network object for streaming from the drone **/
    private var stream: InputStream? = null

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
            delay(500)
        }
    }

    suspend fun wait_to_complete_guided_flight() {
        Log.d(TAG, "Waiting for guided task to complete")
        while (guidedPilotingItf?.get()?.state != Activable.State.IDLE && !cancel) {
            delay(500)
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
                                Log.d(TAG, "Manual interface is unavailable.")
                                // Piloting interface is unavailable.
                            }
                            Activable.State.IDLE -> {
                                Log.d(TAG, "Manual interface is idle.")
                                if (guidedPilotingItf?.get()?.state != Activable.State.ACTIVE || cancel)
                                    it.activate()
                            }
                            Activable.State.ACTIVE -> {
                                Log.d(TAG, "Manual interface is active.")
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
                        Log.d(TAG, "Guided interface is unavailable.")
                        // Piloting interface is unavailable.
                    }
                    Activable.State.IDLE -> {
                        Log.d(TAG, "Guided interface is idle.")
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
    override fun startStreaming(sample_rate: Int?, resolution: Int?) {
        var grabber: FFmpegFrameGrabber = FFmpegFrameGrabber("rtsp://192.168.42.1/live")
        grabber.setOption("rtsp_transport", "udp") // UDP connection
        grabber.setOption("buffer_size", "6000000") // Increase buffer size to allow reading full frames
        grabber.setVideoOption("tune", "fastdecode") // Tune for low compute decoding
        grabber.imageScalingFlags = swscale.SWS_FAST_BILINEAR // Set scaling method

        var width: Int? = null
        var height: Int? = null
        if (resolution == 720) {
            width = 1280
            height = 720
        } else if (resolution == 480) {
            width = 640
            height = 480
        } else {
            throw Exception("Streaming Exception: Unsupported resolution type!")
        }

        grabber.imageWidth = width
        grabber.imageHeight = height

        // Connect to the drone and start streaming
        try {
            grabber.start()
        } catch (e : FFmpegFrameGrabber.Exception) {
            throw Exception("Streaming Exception: " + e.message)
        }

        // Create the grabber wrapper
        wrapper = GrabberWrapper(grabber, width, height)

        // Start grabbing!
        thread = Thread {
            var decodeCounter = 0
            while (true) {
                if (decodeCounter % skip == 0) {
                    decodeCounter = 1
                    // Decode a chunk of frames
                    for (i in 0 until decode) {
                        try {
                            wrapper!!.grab()
                            Log.d(TAG, "Grabbed a frame!")
                        } catch (e: java.lang.Exception) {
                            Log.d(TAG, "Grab Exception: " + e.message)
                        }
                    }
                } else {
                    try {
                        wrapper!!.skip()
                    } catch (e: java.lang.Exception) {
                        Log.d(TAG, "Grab Exception: " + e.message)
                    }
                    decodeCounter += 1
                }
                try {
                    Thread.sleep(1)
                } catch (e: InterruptedException) {
                    e.printStackTrace()
                }
            }
        }
        thread!!.start()
    }

    @Throws(Exception::class)
    override fun stopStreaming() {
        thread!!.interrupt() // Stop the thread
        grabber!!.stop()
        grabber!!.release()
    }

    @Throws(Exception::class)
    override fun getVideoFrame(): ByteArray? {
        var frame: Frame? = wrapper!!.copyFrame() ?: return null
        val baos = ByteArrayOutputStream()
        val bmp: Bitmap = converter.convert(frame)
        bmp.compress(Bitmap.CompressFormat.JPEG, 80, baos)
        return baos.toByteArray()
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
        var countDownLatch = CountDownLatch(1)
        drone?.getInstrument(Gps::class.java) {
            if (it?.lastKnownLocation()?.latitude != null) {
                lat = it.lastKnownLocation()!!.latitude
            }
            countDownLatch.countDown()
        }
        countDownLatch.await()
        return lat
    }

    override fun getLon(): Double? {
        var lon : Double = 0.0
        var countDownLatch = CountDownLatch(1)
        drone?.getInstrument(Gps::class.java) {
            if (it?.lastKnownLocation()?.longitude != null) {
                lon = it.lastKnownLocation()!!.longitude
            }
            countDownLatch.countDown()
        }
        countDownLatch.await()
        return lon
    }

    override fun getAlt(): Double? {
        var alt : Double = 0.0
        var countDownLatch = CountDownLatch(1)
        drone?.getInstrument(Gps::class.java) {
            if (it?.lastKnownLocation()?.altitude != null) {
                alt = it.lastKnownLocation()!!.altitude
            }
            countDownLatch.countDown()
        }
        countDownLatch.await()
        return alt
    }

    @Throws(Exception::class)
    override fun cancel() {
        Log.d(TAG, "Cancelling previous action...")
        TODO("Cancel and wait for all piloting interfaces to disengage")
        // Transfer control back to the flight script
    }

    @Throws(Exception::class)
    override fun kill() {
        cancel = true
        val countDownLatch = CountDownLatch(1)
        pilotingItfRef?.get()?.let { itf ->
            when (itf.state) {
                Activable.State.UNAVAILABLE -> {
                    Log.d(TAG, "Can't do anything.")
                }
                Activable.State.IDLE -> {
                    Log.d(TAG, "Activating itf.")
                    itf.activate()
                    itf.hover()
                }
                Activable.State.ACTIVE -> {
                    Log.d(TAG, "Hovering.")
                    itf.hover()
                }
            }

            countDownLatch.countDown()
        }

        countDownLatch.await()
    }
}