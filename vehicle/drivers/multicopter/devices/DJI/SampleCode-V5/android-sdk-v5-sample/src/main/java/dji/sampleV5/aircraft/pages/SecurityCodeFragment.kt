package dji.sampleV5.aircraft.pages

import android.os.Bundle
import android.text.TextUtils
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.fragment.app.viewModels
import dji.sampleV5.aircraft.R
import dji.sampleV5.aircraft.data.DeviceLockStatus
import dji.sampleV5.aircraft.data.ModifyPasswordBean
import dji.sampleV5.aircraft.databinding.FragAppSilentlyUpgradePageBinding
import dji.sampleV5.aircraft.databinding.FragSecurityCodePageBinding
import dji.sampleV5.aircraft.models.SecurityCodeVM
import dji.sampleV5.aircraft.util.Helper
import dji.sampleV5.aircraft.util.ToastUtils
import dji.sdk.keyvalue.value.flightcontroller.AccessLockerDeviceType
import dji.v5.utils.common.JsonUtil
import dji.v5.utils.common.StringUtils
import dji.v5.ux.core.extension.hide
import dji.v5.ux.core.extension.show

/**
 * Description :安全密码界面，主要演示密码相关功能
 *
 * @author: Byte.Cai
 *  date : 2022/8/10
 *
 * Copyright (c) 2022, DJI All Rights Reserved.
 */
class SecurityCodeFragment : DJIFragment() {
    companion object {
        private const val PASSWORD_MIN_LENGTH = 4//密码最小长度必须为6
        private const val TAG = "SecurityCodeFragment"
        private const val DEVICE_IS_EMPTY = "DeviceList is empty!!!"
    }

    private var binding: FragSecurityCodePageBinding? = null
    private val securityCodeVM: SecurityCodeVM by viewModels()
    private var deviceIndexList = ArrayList<AccessLockerDeviceType>()
    private var currentDeviceStatsList = ArrayList<DeviceLockStatus>()


    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View? {
        binding = FragSecurityCodePageBinding.inflate(inflater, container, false)
        return binding?.root
    }
    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        securityCodeVM.addQueryAllDeviceStatesListener()
        securityCodeVM.deviceStatusListLD.observe(viewLifecycleOwner) {
            binding?.tvDeviceStatusTip?.show()
            binding?.tvDeviceStatus?.text = it.toString()
            deviceIndexList.clear()
            it.forEach { deviceLockStatus: DeviceLockStatus ->
                deviceIndexList.add(deviceLockStatus.deviceIndex)
                if (deviceLockStatus.isFeatureNeedToBeVerified) {
                    binding?.btnVerifyPassword?.show()
                }
            }
            currentDeviceStatsList = it
        }

        securityCodeVM.operationResultTip.observe(viewLifecycleOwner) {
            showProcessBar(false)
            ToastUtils.showToast(it)
        }

        binding?.btnSetPassword?.setOnClickListener {
            setPassword()
        }
        binding?.btnModifyPassword?.setOnClickListener {
            modifyPassword()
        }
        binding?.btnResetPassword?.setOnClickListener {
            resetPassword()
        }
        binding?.btnVerifyPassword?.setOnClickListener {
            verifyPassword()
        }
    }


    private fun showErrorMsg() {
        ToastUtils.showToast("ToBean fail,please try again later!")
    }

    /**
     * 当前设备是否支持SD卡加密
     */
    private fun isDeviceSupportSDLock(index: Int): Boolean {
        return currentDeviceStatsList[index].isFeatureSupported
    }

    /**
     *  当前设备SD卡加密功能是否使能
     */
    private fun isDeviceSDLockEnabled(index: Int): Boolean {
        return isDeviceSupportSDLock(index) && currentDeviceStatsList[index].isFeatureEnabled
    }

    /**
     *  当前设备是否需要SD卡解密
     */
    private fun isCurrentDeviceSDNeedToBeVerified(index: Int): Boolean {
        return isDeviceSDLockEnabled(index) && currentDeviceStatsList[index].isFeatureNeedToBeVerified
    }

    private fun showProcessBar(isShow: Boolean = true) {
        if (isShow && activity?.isFinishing == false) {
            binding?.operateProcess?.show()
        } else {
            binding?.operateProcess?.hide()
        }
    }

    private fun verifyPassword() {
        if (deviceIndexList.isEmpty()) {
            ToastUtils.showToast(DEVICE_IS_EMPTY)
            return
        }
        initPopupNumberPicker(Helper.makeList(deviceIndexList)) {
            val selectedIndex = indexChosen[0]
            if (!isCurrentDeviceSDNeedToBeVerified(selectedIndex)) {
                ToastUtils.showToast(StringUtils.getResStr(R.string.tip_verify_password_fail))
                return@initPopupNumberPicker
            }
            showDialog(StringUtils.getResStr(R.string.tip_set_password)) {
                it?.run {
                    val password = trim()
                    if (!TextUtils.isEmpty(password) && password.length >= PASSWORD_MIN_LENGTH) {
                        showProcessBar()
                        securityCodeVM.verifyPassword(password, deviceIndexList[selectedIndex])
                    } else {
                        ToastUtils.showToast(StringUtils.getResStr(R.string.tip_set_password))
                    }
                }

            }
        }
    }

    private fun resetPassword() {
        if (deviceIndexList.isEmpty()) {
            ToastUtils.showToast(DEVICE_IS_EMPTY)
            return
        }
        initPopupNumberPicker(Helper.makeList(deviceIndexList)) {
            val selectedIndex = indexChosen[0]
            if (!isDeviceSDLockEnabled(selectedIndex)) {
                ToastUtils.showToast(StringUtils.getResStr(R.string.tip_modify_password_not_support))
                return@initPopupNumberPicker
            }
            showDialog(StringUtils.getResStr(R.string.tip_reset_password)) {
                it?.run {
                    showProcessBar()
                    securityCodeVM.resetPassword(deviceIndexList[selectedIndex])
                }
            }

        }
    }

    private fun modifyPassword() {
        if (deviceIndexList.isEmpty()) {
            ToastUtils.showToast(DEVICE_IS_EMPTY)
            return
        }
        initPopupNumberPicker(Helper.makeList(deviceIndexList)) {
            val selectedIndex = indexChosen[0]
            if (!isDeviceSDLockEnabled(selectedIndex)) {
                ToastUtils.showToast(StringUtils.getResStr(R.string.tip_modify_password_not_support))
                return@initPopupNumberPicker
            }
            showDialog(StringUtils.getResStr(R.string.tip_set_password), JsonUtil.toJson(ModifyPasswordBean("", ""))) {
                it?.run {
                    val modifyPasswordBean = trim()
                    val result = JsonUtil.toBean(modifyPasswordBean, ModifyPasswordBean::class.java)
                    if (result == null) {
                        showErrorMsg()
                        return@run
                    }
                    showProcessBar()
                    securityCodeVM.modifyPassword(result, deviceIndexList[selectedIndex])

                }

            }
        }
    }

    private fun setPassword() {
        if (deviceIndexList.isEmpty()) {
            ToastUtils.showToast(DEVICE_IS_EMPTY)
            return
        }
        initPopupNumberPicker(Helper.makeList(deviceIndexList)) {
            val selectedIndex = indexChosen[0]
            if (!isDeviceSupportSDLock(selectedIndex)) {
                ToastUtils.showToast(StringUtils.getResStr(R.string.tip_set_password_not_support))
                return@initPopupNumberPicker
            }
            if (isDeviceSDLockEnabled(selectedIndex)) {
                ToastUtils.showToast(StringUtils.getResStr(R.string.tip_has_set_password_already))
                return@initPopupNumberPicker
            }
            showDialog(StringUtils.getResStr(R.string.tip_set_password)) {
                it?.run {
                    val password = trim()
                    if (!TextUtils.isEmpty(password) && password.length >= PASSWORD_MIN_LENGTH) {
                        showProcessBar()
                        securityCodeVM.setPassword(password, deviceIndexList[selectedIndex])
                    } else {
                        ToastUtils.showToast(StringUtils.getResStr(R.string.tip_set_password))
                    }
                }

            }

        }
    }

}