package dji.v5.ux.obstacle

import android.content.Context
import android.util.AttributeSet
import android.view.LayoutInflater
import dji.v5.utils.common.LogUtils
import dji.v5.utils.common.StringUtils
import dji.v5.ux.R
import dji.v5.ux.core.base.DJISDKModel
import dji.v5.ux.core.base.SchedulerProvider
import dji.v5.ux.core.base.SwitcherCell
import dji.v5.ux.core.base.widget.ConstraintLayoutWidget
import dji.v5.ux.core.communication.ObservableInMemoryKeyedStore
import dji.v5.ux.core.util.ViewUtil
import dji.v5.ux.databinding.UxsdkWidgetVisionPositionWidgetLayoutBinding
import io.reactivex.rxjava3.core.CompletableObserver
import io.reactivex.rxjava3.disposables.Disposable

/**
 * Description :
 *
 * @author: Byte.Cai
 *  date : 2023/8/15
 *
 * Copyright (c) 2022, DJI All Rights Reserved.
 */
private const val TAG = "VisionPositionWidget"

class VisionPositionWidget @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyleAttr: Int = 0,
) : ConstraintLayoutWidget<VisionPositionWidget.ModelState>(context, attrs, defStyleAttr),
    SwitcherCell.OnCheckedChangedListener {
    private var listener: SwitchStateListener? = null
    private lateinit var binding: UxsdkWidgetVisionPositionWidgetLayoutBinding

    private val widgetModel by lazy {
        VisionPositionWidgetModel(DJISDKModel.getInstance(), ObservableInMemoryKeyedStore.getInstance())
    }

    override fun initView(context: Context, attrs: AttributeSet?, defStyleAttr: Int) {
        binding = UxsdkWidgetVisionPositionWidgetLayoutBinding.inflate(LayoutInflater.from(context), this, true)
    }

    override fun reactToModelChanges() {
        addReaction(widgetModel.visionPositionEnableProcessor.toFlowable()
            .observeOn(SchedulerProvider.ui())
            .subscribe { updateVisionSwitchCell(it) })
    }

    override fun onAttachedToWindow() {
        super.onAttachedToWindow()
        if (!isInEditMode) {
            widgetModel.setup()

        }
        binding.omniCommonDownwardsSwitcherCell.setOnCheckedChangedListener(this)
    }

    override fun onDetachedFromWindow() {
        if (!isInEditMode) {
            widgetModel.cleanup()
        }
        super.onDetachedFromWindow()
    }

    override fun getIdealDimensionRatioString(): String? {
        return null
    }

    override fun onCheckedChanged(cell: SwitcherCell?, isChecked: Boolean) {
        if (cell?.id == R.id.omni_common_downwards_switcher_cell) {
            if (!isChecked) {
                val msg = StringUtils.getResStr(context, R.string.uxsdk_setting_ui_omni_perception_desc)
                ViewUtil.showToast(context, msg)
            }

            widgetModel.setVisionPositioningEnabled(isChecked).observeOn(SchedulerProvider.ui())
                .subscribe(object : CompletableObserver {
                    override fun onSubscribe(d: Disposable) {
                        //do nothing
                    }

                    override fun onComplete() {
                        LogUtils.i(TAG, "setVisionPositioningEnabled onComplete!")
                    }

                    override fun onError(e: Throwable) {
                        //do nothing
                        LogUtils.e(TAG, "setVisionPositioningEnabled onError:$e")
                        updateVisionSwitchCell(!isChecked)
                    }
                })
        }
    }

    /**
     * 启用视视觉定位
     * @param enable 开启
     */
    private fun updateVisionSwitchCell(enable: Boolean) {
        LogUtils.i(TAG, "updateVisionSwitchCell:$enable")
        binding.omniCommonDownwardsSwitcherCell.setOnCheckedChangedListener(null)
        binding.omniCommonDownwardsSwitcherCell.isChecked = enable
        binding.omniCommonDownwardsSwitcherCell.setOnCheckedChangedListener(this)
        listener?.onUpdate(enable)
    }

    fun setSwitchStateListener(listener: SwitchStateListener) {
        this.listener = listener
    }


    sealed class ModelState

}