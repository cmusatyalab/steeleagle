package dji.sampleV5.aircraft

import android.app.Application
import android.os.Handler
import android.os.Looper
import android.util.Log
import dji.sampleV5.aircraft.models.MSDKManagerVM
import dji.sampleV5.aircraft.models.globalViewModels
import dji.sdk.keyvalue.key.BatteryKey
import dji.sdk.keyvalue.key.CameraKey
import dji.sdk.keyvalue.key.FlightControllerKey
import dji.sdk.keyvalue.key.KeyTools
import dji.sdk.keyvalue.key.ProductKey
import dji.v5.et.create
import dji.v5.manager.KeyManager
import dji.v5.manager.SDKManager
import dji.v5.manager.interfaces.IKeyManager

/**
 * Class Description
 *
 * @author Hoker
 * @date 2022/3/1
 *
 * Copyright (c) 2022, DJI All Rights Reserved.
 */
open class DJIApplication : Application() {

    private val msdkManagerVM: MSDKManagerVM by globalViewModels()
    private val handler: Handler = Handler(Looper.getMainLooper())


    override fun onCreate() {
        super.onCreate()

        // Ensure initialization is called first
        msdkManagerVM.initMobileSDK(this)
        handler.postDelayed({
            doStuff()
        }, 10000)
    }

    fun doStuff() {
        Log.i("MyApp", "I be here")
        //Log.i("MyApp", "Drone connected with product ID: $prodID")


        // Get the IKeyManager instance from SDKManager
        val keyManager: IKeyManager? = KeyManager.getInstance()
        Log.i("MyApp", "keyManager ${keyManager}")
        Log.i("MyApp", "product category ${SDKManager.getInstance().productCategory}")
        Log.i("MyApp", "battery key ${BatteryKey.KeyChargeRemainingInPercent.create()}")
        val batteryValue =
            KeyManager.getInstance()?.getValue(BatteryKey.KeyChargeRemainingInPercent.create())
        Log.i("MyApp", "Battery level: ${batteryValue ?: "unknown"}%")
        val productKeyConnection =
            KeyManager.getInstance()?.getValue(KeyTools.createKey(ProductKey.KeyConnection))
        val productType =
            KeyManager.getInstance()?.getValue(KeyTools.createKey(ProductKey.KeyProductType))

        Log.i(
            "MyApp",
            "Product Key Connection: ${productKeyConnection} \n Product Type: ${productType}"
        )
        /*KeyManager.getInstance().listen(ProductKey.KeyConnection.create(), object{}, { a: Boolean?, b: Boolean? ->
            Log.i("MyApp", "i'm here in listener")
        })*/

        /*KeyManager.getInstance().listen(KeyTools.createKey(FlightControllerKey.KeyConnection), this, { a: Boolean?, b: Boolean? ->
            Log.i("MyApp", "i'm here in listener ${a} ${b}")

        })*/

        val state = KeyManager.getInstance().getValue(FlightControllerKey.KeyConnection.create())
        Log.i("MyApp", "flight controler connection ${state}")
        val state2 = KeyManager.getInstance().getValue(CameraKey.KeyConnection.create())
        Log.i("MyApp", "camera connection ${state2}")
        val state3 = KeyManager.getInstance().getValue(ProductKey.KeyConnection.create())
        Log.i("MyApp", "product connection ${state3}")
    }

}
