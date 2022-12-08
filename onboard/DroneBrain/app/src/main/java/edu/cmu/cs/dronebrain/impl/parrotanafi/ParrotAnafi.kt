package edu.cmu.cs.dronebrain.impl.parrotanafi

import android.graphics.Bitmap
import android.util.Log
import com.parrot.drone.groundsdk.ManagedGroundSdk
import com.parrot.drone.groundsdk.Ref
import com.parrot.drone.groundsdk.device.Drone
import com.parrot.drone.groundsdk.device.instrument.Altimeter
import com.parrot.drone.groundsdk.device.instrument.FlyingIndicators
import com.parrot.drone.groundsdk.device.instrument.Gps
import com.parrot.drone.groundsdk.device.peripheral.MainCamera
import com.parrot.drone.groundsdk.device.peripheral.MainGimbal
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
import java.util.concurrent.CountDownLatch
import org.apache.commons.math3.geometry.euclidean.threed.Vector3D
import org.apache.commons.math3.geometry.euclidean.threed.Rotation
import org.apache.commons.math3.geometry.euclidean.threed.RotationConvention
import org.apache.commons.math3.geometry.euclidean.threed.RotationOrder
import java.lang.IllegalArgumentException
import java.util.*
import kotlin.collections.ArrayList
import kotlin.math.PI
import kotlin.math.pow
import kotlin.math.roundToInt
import kotlin.math.sign


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
    private var resolution_x: Int = 0
    private var resolution_y: Int = 0
    private var HFOV: Int = 69
    private var VFOV: Int = 43
    /** Tracking target offsets **/
    var dyaw : Double = 0.0
    var dpitch : Double = 0.0
    var droll : Double = 0.0
    var hysteresis_x : Int? = null
    var hysteresis_y : Int? = null
    var timestamp: Long? = null

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
        Log.d(TAG, "moveBy called!");
        var directive = GuidedPilotingItf.RelativeMoveDirective(x, y, z, 0.0, null)

        guidedPilotingItf?.get()?.let {
            it.move(directive)
        }

        runBlocking {
            wait_to_complete_guided_flight()
        }
    }

    @Throws(Exception::class)
    override fun startStreaming(resolution: Int?) {
        var grabber: FFmpegFrameGrabber = FFmpegFrameGrabber("rtsp://192.168.42.1/live")
        grabber.setOption("rtsp_transport", "udp") // UDP connection
        grabber.setOption("buffer_size", "6000000") // Increase buffer size to allow reading full frames
        grabber.setVideoOption("tune", "fastdecode") // Tune for low compute decoding
        grabber.imageScalingFlags = swscale.SWS_FAST_BILINEAR // Set scaling method

        if (resolution == 720) {
            resolution_x = 1280
            resolution_y = 720
        } else if (resolution == 480) {
            resolution_x = 640
            resolution_y = 480
        } else {
            throw Exception("Streaming Exception: Unsupported resolution type!")
        }

        grabber.imageWidth = resolution_x
        grabber.imageHeight = resolution_y

        // Connect to the drone and start streaming
        try {
            grabber.start()
        } catch (e : FFmpegFrameGrabber.Exception) {
            throw Exception("Streaming Exception: " + e.message)
        }

        // Create the grabber wrapper
        wrapper = GrabberWrapper(grabber, resolution_x, resolution_y)

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
                            //Log.d(TAG, "Grabbed a frame!")
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
        val bmp = converter.convert(frame)
        bmp.compress(Bitmap.CompressFormat.JPEG, 80, baos)
        return baos.toByteArray()
    }

    // Drone tracking
    @Throws(Exception::class)
    fun find_intersection(target_direction: Vector3D, altitude_vector: Vector3D): Vector3D {
        var plane_point = Vector3D(0.0, 0.0, 0.0)
        var plane_norm = Vector3D(0.0, 0.0, 1.0)
        if (plane_norm.dotProduct(target_direction).equals(Vector3D.ZERO)) {
            throw IllegalArgumentException()
        }
        var t = (plane_norm.dotProduct(plane_point) - plane_norm.dotProduct(altitude_vector)) / plane_norm.dotProduct(target_direction)
        return altitude_vector.add(target_direction.scalarMultiply(t))
    }

    fun getGimbalPitch(): Double {
        var gimbal_pitch: Double = 0.0
        drone?.getPeripheral(MainGimbal::class.java) {
            gimbal_pitch = it!!.getAttitude(MainGimbal.Axis.PITCH)
        }
        return gimbal_pitch
    }

    fun getMovementVectors(yaw: Double, pitch: Double, leash: Double): Vector3D {
        var gimbal_pitch = getGimbalPitch()
        var altitude = alt
        Log.d("Tracking", "Altitude: " + altitude)
        var forward_vec = Vector3D(0.0, 1.0, 0.0)
        var rotation = Rotation(RotationOrder.ZYX, RotationConvention.VECTOR_OPERATOR, yaw * (PI / 180.0), 0.0, (pitch + gimbal_pitch) * (PI / 180.0))
        var target_direction = rotation.applyTo(forward_vec)
        var target_vector = find_intersection(target_direction, Vector3D(0.0, 0.0, altitude))
        Log.d("Tracking", "Distance estimate to target is " + target_vector.norm)

        var leash_vec: Vector3D?
        if (target_vector.norm > 0.0)
            leash_vec = target_vector.normalize().scalarMultiply(leash)
        else
            leash_vec = target_vector
        var movement_vector = target_vector.subtract(leash_vec)

        return movement_vector
    }

    override fun calculateOffsets(pixel_x: Int, pixel_y: Int, leash: Double): ArrayList<Double> {
        var hysteresis = true
        var pixel_center_x = resolution_x / 2.0
        var pixel_center_y = resolution_y / 2.0
        Log.d("Tracking", "Detection centered at x: " + pixel_x + ", y: " + pixel_y)
        var target_yaw_angle = ((pixel_x - pixel_center_x) / pixel_center_x) * (HFOV / 2.0)
        var target_pitch_angle = ((pixel_y - pixel_center_y) / pixel_center_y) * (VFOV / 2.0)
        Log.d("Tracking", "Yaw angle: " + target_yaw_angle + ", Pitch angle: " + target_pitch_angle)

        // Hysteresis code
        if (hysteresis && timestamp != null && System.currentTimeMillis() - timestamp!! < 2000) {
            var hysteresis_yaw_angle = ((pixel_x - hysteresis_x!!) / hysteresis_x!!) * (HFOV / 2.0)
            var hysteresis_pitch_angle = ((pixel_y - hysteresis_y!!) / hysteresis_y!!) * (VFOV / 2.0)
            target_yaw_angle += hysteresis_yaw_angle * 0.8
            target_pitch_angle += hysteresis_pitch_angle * 0.65
        } else {
            timestamp = System.currentTimeMillis()
            hysteresis_x = pixel_x
            hysteresis_y = pixel_y
        }

        var movement_vector = getMovementVectors(target_yaw_angle, target_pitch_angle, leash)
        var drone_roll = movement_vector.x
        var drone_pitch = movement_vector.y
        Log.d("Tracking", "Roll amount: " + drone_roll + ", Pitch amount: " + drone_pitch)

        var returnVector = ArrayList<Double>()
        returnVector.add(target_pitch_angle)
        returnVector.add(target_yaw_angle)
        returnVector.add(drone_pitch)
        returnVector.add(drone_roll)

        return returnVector
    }

    fun gain(drone_yaw: Double, drone_pitch: Double, drone_roll: Double): ArrayList<Double> {
        var dyaw = (drone_yaw).coerceIn(-100.0, 100.0) //3.0
        var dpitch = (drone_pitch).coerceIn(-100.0, 100.0) //15.0
        var droll = (drone_roll).coerceIn(-100.0, 100.0)

        var returnVector = ArrayList<Double>()
        returnVector.add(dyaw)
        returnVector.add(dpitch)
        returnVector.add(droll)

        return returnVector
    }

    fun executePCMD(gimbal_pitch: Double?, drone_yaw: Double, drone_pitch: Double, drone_roll: Double) {
        var returnVector = gain(drone_yaw, drone_pitch, drone_roll)
        var gpitch = gimbal_pitch
        var dyaw = returnVector[0].roundToInt()
        var dpitch = returnVector[1].roundToInt()
        var droll = returnVector[2].roundToInt()

        if (gpitch != null) setGimbalPose(0.0, ((gpitch / 1.5) + getGimbalPitch()).coerceIn(-90.0, 90.0), 0.0)
        pilotingItfRef?.get()?.let {
            it.setYawRotationSpeed(dyaw)
            it.setPitch(-1 * dpitch)
        }
    }

    @Throws(Exception::class)
    override fun trackTarget(box: Vector<Double>?, leash: Double) {
        var gpitch : Double? = null
        if (box != null) {
            Log.d("Tracking", "Got box for target class!")
            // Find the pixel center
            var pixel_x = ((((box[3] - box[1]) / 2.0) + box[1]) * resolution_x).roundToInt()
            var pixel_y = ((1 - (((box[2] - box[0]) / 2.0) + box[0])) * resolution_y).roundToInt()
            // Get offsets
            var offsets = calculateOffsets(pixel_x, pixel_y, leash)
            //gpitch = offsets[0]
            dyaw = offsets[1]
            dyaw *= 30.0
            dpitch = offsets[2]
            dpitch *= 20.0
            droll = offsets[3]
        } else {
            //dyaw /= 1.225 //1.065
            dyaw /= 1.23
            dpitch /= 1.155
            droll /= 1.01
        }

        executePCMD(gpitch, dyaw, dpitch, droll)
    }

    @Throws(Exception::class)
    override fun lookAtTarget(box: Vector<Double>?) {
        var gpitch : Double? = null
        if (box != null) {
            Log.d("Tracking", "Got box for target class!")
            // Find the pixel center
            var pixel_x = ((((box[3] - box[1]) / 2.0) + box[1]) * resolution_x).roundToInt()
            var pixel_y = ((1 - (((box[2] - box[0]) / 2.0) + box[0])) * resolution_y).roundToInt()
            // Get offsets
            var offsets = calculateOffsets(pixel_x, pixel_y, 1.0)
            gpitch = offsets[0]
            dyaw = offsets[1]
            dyaw *= 20.0
            pilotingItfRef?.get()?.let { if (alt > 6.0) it.setVerticalSpeed(-15) else it.setVerticalSpeed(0) }
        } else {
            dyaw /= 1.135
        }

        executePCMD(gpitch, dyaw, 0.0, 0.0)
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
        throw NotImplementedError()
    }

    @Throws(Exception::class)
    override fun setGimbalPose(yaw_theta: Double?, pitch_theta: Double?, roll_theta: Double?) {
        drone?.getPeripheral(MainGimbal::class.java) {
            it?.control(MainGimbal.ControlMode.POSITION, yaw_theta, pitch_theta, roll_theta)
        }
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
    override fun getName(): String {
        var name : String = "Unnamed"
        if (drone?.name != null)
            name = drone!!.name
        return name
    }

    override fun getLat(): Double {
        var lat : Double = 0.0
        drone?.getInstrument(Gps::class.java) {
            if (it?.lastKnownLocation()?.latitude != null) {
                lat = it.lastKnownLocation()!!.latitude
            }
        }
        return lat
    }

    override fun getLon(): Double {
        var lon : Double = 0.0
        drone?.getInstrument(Gps::class.java) {
            if (it?.lastKnownLocation()?.longitude != null) {
                lon = it.lastKnownLocation()!!.longitude
            }
        }
        return lon
    }

    override fun getAlt(): Double {
        var alt : Double = 0.0
        drone?.getInstrument(Altimeter::class.java) {
            alt = it!!.takeOffRelativeAltitude
        }
        return alt
    }

    override fun hover() {
        pilotingItfRef?.get()?.let { itf ->
            when (itf.state) {
                Activable.State.UNAVAILABLE -> {
                    Log.d(TAG, "Can't do anything.")
                }
                Activable.State.IDLE -> {
                    Log.d(TAG, "Activating itf.")
                    itf.activate()
                }
                Activable.State.ACTIVE -> {
                    Log.d(TAG, "Hovering.")
                    itf.hover()
                }
            }
        }
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
        hover()
    }
}