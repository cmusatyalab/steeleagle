package dji.sampleV5.aircraft;

import static dji.sdk.keyvalue.key.co_z.KeyCompassHeading;
import static dji.sdk.keyvalue.key.co_z.KeyGPSSatelliteCount;

import android.content.Intent;
import android.os.Bundle;
import android.util.Log;
import android.widget.Button;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import dji.sdk.keyvalue.key.BatteryKey;
import dji.sdk.keyvalue.key.DJIKey;
import dji.sdk.keyvalue.key.FlightControllerKey;
import dji.sdk.keyvalue.key.GimbalKey;
import dji.sdk.keyvalue.key.ProductKey;
import dji.sdk.keyvalue.value.camera.CameraMode;
import dji.sdk.keyvalue.value.common.Attitude;
import dji.sdk.keyvalue.value.common.LocationCoordinate2D;
import dji.sdk.keyvalue.value.common.Velocity3D;
import dji.sdk.keyvalue.value.flightcontroller.CompassCalibrationState;
import dji.sdk.keyvalue.value.product.ProductType;
import dji.v5.common.callback.CommonCallbacks;
import dji.v5.common.register.PackageProductCategory;
import dji.v5.common.utils.CallbackUtils;
import dji.v5.common.utils.RxUtil;
import dji.v5.manager.KeyManager;
import dji.sdk.keyvalue.key.CameraKey;
import dji.sdk.keyvalue.key.KeyTools;
import dji.v5.manager.SDKManager;
import dji.v5.manager.interfaces.IKeyManager;
import io.reactivex.rxjava3.core.Completable;

public class MyActivity extends AppCompatActivity {

    private static final String TAG = "MyActivity";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.my_activity);

        // Back button behavior
        Button backButton = findViewById(R.id.back_button);
        backButton.setOnClickListener(v -> {
            Log.i("MyApp", "Back button clicked");
            Intent intent = new Intent(MyActivity.this, DJIMainActivity.class);
            intent.setFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
            startActivity(intent);
            finish();
        });

        // Photo button behavior
        Button photoButton = findViewById(R.id.photo_button);
        photoButton.setOnClickListener(v -> takePhoto());

        // Gimbal rotate vertical button behavior
        Button gimbalV = findViewById(R.id.gimbal_v_button);
        gimbalV.setOnClickListener(v -> gimbalVertical());

        // Gimbal rotate horizontal button button behavior
        Button gimbalH = findViewById(R.id.gimbal_h_button);
        gimbalH.setOnClickListener(v -> gimbalHorizontal());

        // Battery button behavior
        Button batteryButton = findViewById(R.id.battery_button);
        batteryButton.setOnClickListener(v -> getBattery());

        // Name button behavior
        Button nameButton = findViewById(R.id.name_button);
        nameButton.setOnClickListener(v -> getName());

        // Get global position button behavior
        Button globalPositionButton = findViewById(R.id.global_position_button);
        globalPositionButton.setOnClickListener(v -> getGlobalPosition());

        // Get altitude button behavior
        Button altitudeButton = findViewById(R.id.altitude_button);
        altitudeButton.setOnClickListener(v -> getAltitude());

        // Get attitude button behavior
        Button attitudeButton = findViewById(R.id.attitude_button);
        attitudeButton.setOnClickListener(v -> getAttitude());

        // Get satellite button behavior
        Button satelliteButton = findViewById(R.id.satellite_button);
        satelliteButton.setOnClickListener(v -> getSatellite());

        // Get heading button behavior
        Button headingButton = findViewById(R.id.heading_button);
        headingButton.setOnClickListener(v -> getHeading());

        // Get magnetometer button behavior
        Button magnetometerButton = findViewById(R.id.magnetometer_button);
        magnetometerButton.setOnClickListener(v -> getMagnetometer());

        // Get velocity enu button behavior
        Button velocityENUButton = findViewById(R.id.velocity_enu_button);
        velocityENUButton.setOnClickListener(v -> getVelocityENU());
    }


    /*private void takePhoto() {
        RxUtil.setValue(KeyTools.createKey(CameraKey.KeyCameraMode), CameraMode.PHOTO_NORMAL).andThen
                (RxUtil.performActionWithOutResult(KeyTools.createKey(CameraKey.KeyStartShootPhoto))).subscribe();
        Log.i("MyApp", "Took photo");
    }*/
    private void takePhoto() {
        IKeyManager keyPhoto = KeyManager.getInstance();
        keyPhoto.setValue(KeyTools.createKey(CameraKey.KeyCameraMode), CameraMode.PHOTO_NORMAL, null);
        keyPhoto.performAction(KeyTools.createKey(CameraKey.KeyStartShootPhoto), null);
        Log.i("MyApp", "Took photo");
    }

    private void gimbalVertical() {
        IKeyManager keyGimbalV = KeyManager.getInstance();
        keyGimbalV.setValue(KeyTools.createKey(GimbalKey.KeyGimbalVerticalShotEnabled), true, null);
        Log.i("MyApp", "Rotate gimbal vertical");

    }

    private void gimbalHorizontal() {
        IKeyManager keyGimbalV = KeyManager.getInstance();
        keyGimbalV.setValue(KeyTools.createKey(GimbalKey.KeyGimbalVerticalShotEnabled), false, null);
        Log.i("MyApp", "Rotate gimbal horizontal");
    }

    private void getBattery() {
        IKeyManager keyBattery = KeyManager.getInstance();
        Integer batteryValue = keyBattery.getValue(KeyTools.createKey(BatteryKey.KeyChargeRemainingInPercent));
        TextView textView = findViewById(R.id.main_text);
        textView.setText("Battery: " + batteryValue + "%");
        Log.i("MyApp", "Sent battery level remaining");
    }

    private void getName() {
        IKeyManager keyName = KeyManager.getInstance();
        ProductType nameValue = keyName.getValue(KeyTools.createKey(ProductKey.KeyProductType));
        TextView textView = findViewById(R.id.main_text);
        textView.setText("Name: " + nameValue);
        Log.i("MyApp", "Sent name");
    }

    private void getGlobalPosition() {
        IKeyManager keyManager = KeyManager.getInstance();
        LocationCoordinate2D gpsLocation = keyManager.getValue(KeyTools.createKey(FlightControllerKey.KeyAircraftLocation));
        TextView textView = findViewById(R.id.main_text);
        if (gpsLocation != null) {
            double lat = gpsLocation.getLatitude();
            double lon = gpsLocation.getLongitude();
            textView.setText("Lat: " + lat + "\nLon: " + lon);
            Log.i("MyApp", "GPS: " + "Lat: " + lat + "\nLon: " + lon);
        } else {
            textView.setText("GPS data not available");
            Log.w("MyApp", "GPS location is null");
        }
    }

    private void getAltitude() {
        IKeyManager keyManager = KeyManager.getInstance();
        Double altitude = keyManager.getValue(KeyTools.createKey(FlightControllerKey.KeyAltitude));
        TextView textView = findViewById(R.id.main_text);
        if (altitude != null) {
            textView.setText("Altitude: " + altitude);
            Log.i("MyApp", "Altitude: " + altitude);
        } else {
            textView.setText("Altitude not available");
            Log.w("MyApp", "Altitude is null");
        }
    }

    private void getAttitude() {
        IKeyManager keyManager = KeyManager.getInstance();
        Attitude attitude = keyManager.getValue(KeyTools.createKey(FlightControllerKey.KeyAircraftAttitude));
        TextView textView = findViewById(R.id.main_text);
        if (attitude != null) {
            textView.setText("Attitude: " + attitude);
            Log.i("MyApp", "Attitude: " + attitude);
        } else {
            textView.setText("Attitude not available");
            Log.w("MyApp", "Attitude is null");
        }
    }

    private void getSatellite() {
        IKeyManager keyManager = KeyManager.getInstance();
        Integer satellite = keyManager.getValue(KeyTools.createKey(KeyGPSSatelliteCount));
        TextView textView = findViewById(R.id.main_text);
        if (satellite != null) {
            textView.setText("Satellite count: " + satellite);
            Log.i("MyApp", "Satellite count: " + satellite);
        } else {
            textView.setText("Satellite count not available");
            Log.w("MyApp", "Satellite count is null");
        }
    }

    private void getHeading() {
        // Gets the compass heading
        // Uses units of degrees
        // North is 0 degrees & East is 90 degrees by default
        // The value range for the compass degrees is -180 to 180
        IKeyManager keyManager = KeyManager.getInstance();
        Double heading = keyManager.getValue(KeyTools.createKey(KeyCompassHeading));
        TextView textView = findViewById(R.id.main_text);
        if (heading != null) {
            textView.setText("Heading: " + heading);
            Log.i("MyApp", "Heading: " + heading);
        } else {
            textView.setText("Heading not available");
            Log.w("MyApp", "Heading is null");
        }
    }

    private void getMagnetometer() {
        // IDLE: normal status, the compass is not calibrated
        // HORIZONTAL: the horizontal calibration of the compass where the user should hold the drone horizontally and rotate it 360 degrees
        // VERTICAL: the vertical calibration of the compass where the user should hold the drone vertically and rotate it 360 degrees
        // SUCCEEDED: compass calibration was successful
        // FAILED: compass calibration failed (should make sure there re no magnets or metal objects near the drone and try again)
        IKeyManager keyManager = KeyManager.getInstance();
        CompassCalibrationState compassCalibration = keyManager.getValue(KeyTools.createKey(FlightControllerKey.KeyCompassCalibrationStatus));
        TextView textView = findViewById(R.id.main_text);
        if (compassCalibration != null) {
            textView.setText("Magnetometer: " + compassCalibration);
            Log.i("MyApp", "Heading: " + compassCalibration);
        } else {
            textView.setText("Magnetometer not available");
            Log.w("MyApp", "Magnetometer is null");
        }
    }

    private void getVelocityENU() {
        // KeyAircraftVelocity by default gets values using NED (north, east, down) coordinates
        // This function should transfer these coordinates to the desired ENU (east, north, up) coordinates
        IKeyManager keyManager = KeyManager.getInstance();
        Velocity3D velocity = keyManager.getValue(KeyTools.createKey(FlightControllerKey.KeyAircraftVelocity));
        TextView textView = findViewById(R.id.main_text);
        if (velocity != null) {
            double east = velocity.getY();
            double north = velocity.getX();
            double up = -velocity.getZ();
            textView.setText("East: " + east + "\nNorth: " + north + "\nUp: " + up);
            Log.i("MyApp", "East: " + east + "\nNorth: " + north + "\nUp: " + up);
        } else {
            textView.setText("Velocity not available");
            Log.w("MyApp", "Velocity is null");
        }
    }

    //_get_velocity_body
    //_get_current_status
    //_get_gimbal_pose_body

}



