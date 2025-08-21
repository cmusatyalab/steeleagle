package dji.sampleV5.aircraft.models

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.DocumentsContract
import dji.v5.manager.aircraft.flightrecord.FlightLogManager

/**
 * Description : FLightReecordVM
 * Author : daniel.chen
 * CreateDate : 2021/7/15 10:51 上午
 * Copyright : ©2021 DJI All Rights Reserved.
 */
class FlightRecordVM : DJIViewModel() {
    fun getFlightLogPath(): String {
        return FlightLogManager.getInstance().flightRecordPath
    }

    fun getFlyClogPath(): String {
        return FlightLogManager.getInstance().flyClogPath
    }
}