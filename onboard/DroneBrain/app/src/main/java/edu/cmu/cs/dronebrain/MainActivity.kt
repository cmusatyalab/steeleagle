package edu.cmu.cs.dronebrain

import android.app.Activity
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import android.os.Bundle
import android.os.StrictMode
import android.os.StrictMode.ThreadPolicy
import android.util.Log
import android.widget.Button
import android.widget.TextView
import com.parrot.drone.groundsdk.GroundSdk
import com.parrot.drone.groundsdk.ManagedGroundSdk
import com.parrot.drone.groundsdk.Ref
import com.parrot.drone.groundsdk.device.DeviceState
import com.parrot.drone.groundsdk.device.Drone
import com.parrot.drone.groundsdk.device.RemoteControl
import com.parrot.drone.groundsdk.device.instrument.BatteryInfo
import com.parrot.drone.groundsdk.device.instrument.Gps
import com.parrot.drone.groundsdk.device.pilotingitf.Activable
import com.parrot.drone.groundsdk.device.pilotingitf.ManualCopterPilotingItf
import com.parrot.drone.groundsdk.facility.AutoConnection
import dalvik.system.DexClassLoader
import edu.cmu.cs.dronebrain.impl.ParrotAnafi
import edu.cmu.cs.dronebrain.impl.DebugCloudlet
import edu.cmu.cs.dronebrain.interfaces.FlightScript
import edu.cmu.cs.dronebrain.interfaces.Platform
import java.io.*
import java.net.HttpURLConnection
import java.net.URL

class MainActivity : Activity() {

    /** GroundSdk instance. */
    private lateinit var groundSdk: GroundSdk

    // Drone:
    /** Current drone instance. */
    private var drone: Drone? = null
    /** Reference to the current drone state. */
    private var droneStateRef: Ref<DeviceState>? = null
    /** Reference to the current drone battery info instrument. */
    private var droneBatteryInfoRef: Ref<BatteryInfo>? = null
    /** Reference to a current drone piloting interface. */
    private var pilotingItfRef: Ref<ManualCopterPilotingItf>? = null

    // Remote control:
    /** Current remote control instance. */
    private var rc: RemoteControl? = null
    /** Reference to the current remote control state. */
    private var rcStateRef: Ref<DeviceState>? = null
    /** Reference to the current remote control battery info instrument. */
    private var rcBatteryInfoRef: Ref<BatteryInfo>? = null

    // User Interface:
    /** Drone state text view. */
    private lateinit var droneStateTxt: TextView
    /** Drone battery level text view. */
    private lateinit var droneBatteryTxt: TextView
    /** Remote state level text view. */
    private lateinit var rcStateTxt: TextView
    /** Remote battery level text view. */
    private lateinit var rcBatteryTxt: TextView
    /** Take off / land button. */
    private lateinit var takeOffLandBt: Button
    /** Network for using LTE **/
    private lateinit var network: Network
    /** URL connection to transponder over LTE **/
    private lateinit var con: HttpURLConnection

    val TAG = "TAG"

    @Throws(Exception::class)
    fun getDrone(platform: Platform) : edu.cmu.cs.dronebrain.interfaces.Drone? {
        return if (platform == Platform.ANAFI) {
            ParrotAnafi()
        } else {
            throw Exception("Unsupported drone platfrom")
        }
    }

    fun getCloudlet() : edu.cmu.cs.dronebrain.interfaces.Cloudlet {
        return DebugCloudlet()
    }

    fun download(url: String?, dex: File?) {
        var bis: BufferedInputStream? = null
        var bos: BufferedOutputStream? = null
        try {
            val urlObject = URL(url)
            val httpConn = urlObject.openConnection() as HttpURLConnection
            val responseCode = httpConn.responseCode
            if (responseCode != HttpURLConnection.HTTP_OK) {
                throw RuntimeException("Download didn't work, http status: $responseCode")
            }
            bis = BufferedInputStream(httpConn.inputStream)
            bos = BufferedOutputStream(FileOutputStream(dex))
            copy(bis, bos)
        } catch (e: IOException) {
            throw RuntimeException(e)
        } finally {
            //closeQuietly(bos!!, bis!!)
        }
    }

    @Throws(IOException::class)
    private fun copy(src: BufferedInputStream, dst: OutputStream) {
        var len: Int
        val buf = ByteArray(8 * 1024)
        while (src.read(buf, 0, 8 * 1024).also { len = it } > 0) {
            dst.write(buf, 0, len)
        }
    }

    private fun closeQuietly(vararg cls: Closeable) {
        for (cl in cls) {
            if (cl != null) {
                try {
                    cl.close()
                } catch (ignored: IOException) {
                }
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        val policy = ThreadPolicy.Builder().permitAll().build()
        StrictMode.setThreadPolicy(policy)

        // Get user interface instances.
        droneStateTxt = findViewById(R.id.droneStateTxt)
        droneBatteryTxt = findViewById(R.id.droneBatteryTxt)
        rcStateTxt = findViewById(R.id.rcStateTxt)
        rcBatteryTxt = findViewById(R.id.rcBatteryTxt)
        takeOffLandBt = findViewById(R.id.takeOffLandBt)
        takeOffLandBt.setOnClickListener {onTakeOffLandClick()}

        // Initialize user interface default values.
        droneStateTxt.text = DeviceState.ConnectionState.DISCONNECTED.toString()
        rcStateTxt.text = DeviceState.ConnectionState.DISCONNECTED.toString()

        // Get a GroundSdk session.
        groundSdk = ManagedGroundSdk.obtainSession(this)
        // All references taken are linked to the activity lifecycle and
        // automatically closed at its destruction.

        val context = applicationContext
        val cm = context.getSystemService(
            CONNECTIVITY_SERVICE) as ConnectivityManager
        val req = NetworkRequest.Builder()
        req.addTransportType(NetworkCapabilities.TRANSPORT_CELLULAR)
        cm.requestNetwork(req.build(), object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(net: Network) {
                network = net
                val url = URL("http://steel-eagle-dashboard.pgh.cloudapp.azurelel.cs.cmu.edu:8080/update")
                con = net.openConnection(url) as HttpURLConnection
                con.requestMethod = "POST"
                con.setRequestProperty("Content-Type", "application/json; utf-8")
                con.setRequestProperty("Accept", "application/json")
                con.doOutput = true
            } // Be sure to override other options in NetworkCallback() too...
        }
        )

        val f = File(getDir("dex", MODE_PRIVATE), "classes.dex")
        download("http://cloudlet040.elijah.cs.cmu.edu/classes.dex", f)

        val classLoader = DexClassLoader(
            f.absolutePath, getDir("outdex", MODE_PRIVATE).absolutePath, null,
            classLoader
        )

        try {
            val clazz = classLoader.loadClass("edu.cmu.cs.dronebrain.MS")
            Log.i(TAG, clazz.toString())
            Log.i(TAG, clazz.canonicalName)
            val inst = clazz.newInstance() as FlightScript
            Log.i(TAG, inst.toString())
            Log.i(TAG, inst.toString())
            val drone = getDrone(inst.platform) // Get the corresponding drone
            val cloudlet = getCloudlet() // Get the corresponding cloudlet
            inst.run(drone, cloudlet);
        } catch (e: java.lang.Exception) {
            Log.e(TAG, e.toString())
        }
    }

    override fun onStart() {
        super.onStart()

        // Monitor the auto connection facility.
        groundSdk.getFacility(AutoConnection::class.java) {
            // Called when the auto connection facility is available and when it changes.

            it?.let{
                // Start auto connection.
                if (it.status != AutoConnection.Status.STARTED) {
                    it.start()
                }

                // If the drone has changed.
                if (drone?.uid != it.drone?.uid) {
                    if(drone != null) {
                        // Stop monitoring the old drone.
                        stopDroneMonitors()

                        // Reset user interface drone part.
                        resetDroneUi()
                    }

                    // Monitor the new drone.
                    drone = it.drone
                    if(drone != null) {
                        startDroneMonitors()
                    }
                }

                // If the remote control has changed.
                if (rc?.uid  != it.remoteControl?.uid) {
                    if(rc != null) {
                        // Stop monitoring the old remote.
                        stopRcMonitors()

                        // Reset user interface Remote part.
                        resetRcUi()
                    }

                    // Monitor the new remote.
                    rc = it.remoteControl
                    if(rc != null) {
                        startRcMonitors()
                    }
                }
            }
        }
    }

    /**
     * Resets drone user interface part.
     */
    private fun resetDroneUi() {
        // Reset drone user interface views.
        droneStateTxt.text = DeviceState.ConnectionState.DISCONNECTED.toString()
        droneBatteryTxt.text = ""
        takeOffLandBt.isEnabled = false
    }

    /**
     * Starts drone monitors.
     */
    private fun startDroneMonitors() {
        // Monitor drone state.
        monitorDroneState()

        // Monitor drone battery level.
        monitorDroneBatteryLevel()

        // Monitor piloting interface.
        monitorPilotingInterface()

        transponder()
    }

    /**
     * Stops drone monitors.
     */
    private fun stopDroneMonitors() {
        // Close all references linked to the current drone to stop their monitoring.

        droneStateRef?.close()
        droneStateRef = null

        droneBatteryInfoRef?.close()
        droneBatteryInfoRef = null

        pilotingItfRef?.close()
        pilotingItfRef = null
    }

    /**
     * Monitor current drone state.
     */
    private fun monitorDroneState() {
        // Monitor current drone state.
        droneStateRef = drone?.getState {
            // Called at each drone state update.

            it?.let {
                // Update drone connection state view.
                droneStateTxt.text = it.connectionState.toString()
            }
        }
    }

    /**
     * Monitors current drone battery level.
     */
    private fun monitorDroneBatteryLevel() {
        // Monitor the battery info instrument.
        droneBatteryInfoRef = drone?.getInstrument(BatteryInfo::class.java) {
            // Called when the battery info instrument is available and when it changes.

            it?.let {
                // Update drone battery level view.
                droneBatteryTxt.text = "${it.batteryLevel}"
            }
        }
    }

    /**
     * Monitors current drone piloting interface.
     */
    private fun monitorPilotingInterface() {
        // Monitor a piloting interface.
        pilotingItfRef = drone?.getPilotingItf(ManualCopterPilotingItf::class.java) {
            // Called when the manual copter piloting Interface is available
            // and when it changes.

            // Disable the button if the piloting interface is not available.
            if (it == null) {
                takeOffLandBt.isEnabled = false
            } else {
                managePilotingItfState(it)
            }
        }
    }

    /**
     * Transponder
     */
    private fun transponder() {
        var lat : Double?
        var lon : Double?
        var alt : Double?
        // Monitor the GPS interface
        drone?.getInstrument(Gps::class.java) {
            it?.let {
                lat = it.lastKnownLocation()?.latitude
                lon = it.lastKnownLocation()?.longitude
                alt = it.lastKnownLocation()?.altitude
                Log.d("Drone", "Updating location $lat, $lon, $alt")
                if (lat != null && lon != null && alt != null) {
                    /** Make POST request with new data */
                    try {
                        var jsonInputString =
                            "{\"data\": {\"tag\": \"Anafi\", \"lat\":$lat, \"lng\":$lon, \"alt\":$alt, \"spd\":0, \"state\":\"Flying\", \"plan\":[]}, \"droneid\":\"Anafi\"}"
                        try {
                            val outputStream = DataOutputStream(con.outputStream)
                            outputStream.write(jsonInputString.toByteArray(charset("utf-8")))
                            outputStream.flush()
                        } catch (exception: Exception) {
                        }
                        Log.v("Drone", con.responseCode.toString())
                        val inputStream = DataInputStream(con.inputStream)
                        val reader: BufferedReader = BufferedReader(InputStreamReader(inputStream))
                        val output: String = reader.readLine()
                        Log.d("Drone", jsonInputString)
                    }
                    catch (e : Exception) {
                        Log.d("Exception", e.toString())
                    }
                }
            }
        }
    }


    /**
     * Manage piloting interface state.
     *
     * @param itf the piloting interface
     */
    private fun managePilotingItfState(itf: ManualCopterPilotingItf) {
        when(itf.state) {
            Activable.State.UNAVAILABLE -> {
                // Piloting interface is unavailable.
                takeOffLandBt.isEnabled = false
            }

            Activable.State.IDLE -> {
                // Piloting interface is idle.
                takeOffLandBt.isEnabled = false

                // Activate the interface.
                itf.activate()
            }

            Activable.State.ACTIVE -> {
                // Piloting interface is active.

                when {
                    itf.canTakeOff() -> {
                        // Drone can take off.
                        takeOffLandBt.isEnabled = true
                        takeOffLandBt.text = "Take Off"
                    }
                    itf.canLand() -> {
                        // Drone can land.
                        takeOffLandBt.isEnabled = true
                        takeOffLandBt.text = "Land"
                    }
                    else -> // Disable the button.
                        takeOffLandBt.isEnabled = false
                }
            }
        }
    }

    /**
     * Called on take off/land button click.
     */
    private fun onTakeOffLandClick() {
        // Get the piloting interface from its reference.
        pilotingItfRef?.get()?.let { itf ->
            // Do the action according to the interface capabilities
            if (itf.canTakeOff()) {
                // Take off
                itf.takeOff()
            } else if (itf.canLand()) {
                // Land
                itf.land()
            }
        }
    }

    /**
     * Resets remote user interface part.
     */
    private fun resetRcUi() {
        // Reset remote control user interface views.
        rcStateTxt.text = DeviceState.ConnectionState.DISCONNECTED.toString()
        rcBatteryTxt.text = ""
    }

    /**
     * Starts remote control monitors.
     */
    private fun startRcMonitors() {
        // Monitor remote state
        monitorRcState()

        // Monitor remote battery level
        monitorRcBatteryLevel()
    }

    /**
     * Stops remote control monitors.
     */
    private fun stopRcMonitors() {
        // Close all references linked to the current remote to stop their monitoring.

        rcStateRef?.close()
        rcStateRef = null

        rcBatteryInfoRef?.close()
        rcBatteryInfoRef = null
    }

    /**
     * Monitor current remote control state.
     */
    private fun monitorRcState() {
        // Monitor current drone state.
        rcStateRef = rc?.getState {
            // Called at each remote state update.

            it?.let {
                // Update remote connection state view.
                rcStateTxt.text = it.connectionState.toString()
            }
        }
    }

    /**
     * Monitors current remote control battery level.
     */
    private fun monitorRcBatteryLevel() {
        // Monitor the battery info instrument.
        rcBatteryInfoRef = rc?.getInstrument(BatteryInfo::class.java) {
            // Called when the battery info instrument is available and when it changes.

            it?.let {
                // Update drone battery level view.
                rcBatteryTxt.text = "${it.batteryLevel}"
            }
        }
    }
}
