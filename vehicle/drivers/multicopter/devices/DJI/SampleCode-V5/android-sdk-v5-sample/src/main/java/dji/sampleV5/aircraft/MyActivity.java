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
import dji.sdk.keyvalue.key.PayloadKey;
import dji.sdk.keyvalue.key.ProductKey;
import dji.sdk.keyvalue.value.camera.CameraMode;
import dji.sdk.keyvalue.value.common.Attitude;
import dji.sdk.keyvalue.value.common.EmptyMsg;
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

        // Get takeoff button behavior
        Button takeoffButton = findViewById(R.id.takeoff_button);
        takeoffButton.setOnClickListener(v -> startTakeoff());

        // Get landing button behavior
        Button landingButton = findViewById(R.id.landing_button);
        landingButton.setOnClickListener(v -> startLanding());

        // Get velocity body button behavior
        Button velocityBodyButton = findViewById(R.id.velocity_body_button);
        velocityBodyButton.setOnClickListener(v -> getVelocityBody());

        // Get gimbal pose body button behavior
        Button gimbalPoseButton = findViewById(R.id.gimbal_pose_button);
        gimbalPoseButton.setOnClickListener(v -> gimbalPoseBody());

        // Get gimbal pose body button behavior
        //Button setGimbalButton = findViewById(R.id.set_gimbal_position_button);
        //setGimbalButton.setOnClickListener(v -> setGimbalPosition());

        // Get status body button behavior
        Button statusButton = findViewById(R.id.status_button);
        statusButton.setOnClickListener(v -> getStatus());

        // Type button behavior
        Button typeButton = findViewById(R.id.type_button);
        typeButton.setOnClickListener(v -> getType());

        // Set home using current location button behavior
        Button currentLocationHomeButton = findViewById(R.id.set_home_current_location);
        currentLocationHomeButton.setOnClickListener(v -> setHomeCurrentLocation());

        // Set go home using current location button behavior
        Button startGoHomeButton = findViewById(R.id.start_go_home);
        startGoHomeButton.setOnClickListener(v -> startGoHome());
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
        String nameValue = keyName.getValue(KeyTools.createKey(FlightControllerKey.KeySerialNumber));
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

    private void getVelocityBody() {
        IKeyManager keyManager = KeyManager.getInstance();
        Velocity3D velocity = keyManager.getValue(KeyTools.createKey(FlightControllerKey.KeyAircraftVelocity));
        Double heading = keyManager.getValue(KeyTools.createKey(FlightControllerKey.KeyCompassHeading));
        TextView textView = findViewById(R.id.main_text);

        if (velocity != null && heading != null) {
            // Convert ENU velocity to north, east, up (since DJI uses NED by default)
            double north = velocity.getX();
            double east = velocity.getY();
            double up = -velocity.getZ();  // ENU to NED conversion: flip z-axis

            // 2D velocity vector in the horizontal plane (north, east)
            double[] vec = { north, east };

            // Calculate rotation for forward vector by heading + 90 degrees
            double hd = heading + 90.0;
            double fwRad = Math.toRadians(hd);  // Convert to radians
            double cosFw = Math.cos(fwRad);
            double sinFw = Math.sin(fwRad);
            double[] vecf = { cosFw * 0.0 - sinFw * 1.0, sinFw * 0.0 + cosFw * 1.0 };

            // Calculate rotation for right vector (heading + 90 degrees)
            double rtRad = Math.toRadians(hd + 90.0);  // Heading + 90 degrees for right vector
            double cosRt = Math.cos(rtRad);
            double sinRt = Math.sin(rtRad);
            double[] vecr = { cosRt * 0.0 - sinRt * 1.0, sinRt * 0.0 + cosRt * 1.0 };

            // Calculate dot products for forward and right velocity components
            double forward = - (vec[0] * vecf[0] + vec[1] * vecf[1]);
            double right = - (vec[0] * vecr[0] + vec[1] * vecr[1]);

            // Log the body velocities (forward, right, up)
            textView.setText(String.format("Forward: %.2f, Right: %.2f, Up: %.2f", forward, right, up));
            Log.i("VelocityBody", String.format("Forward: %.2f, Right: %.2f, Up: %.2f", forward, right, up));
        } else {
            textView.setText("Velocity or Heading not available");
            Log.w("VelocityBody", "Velocity or Heading not available");
        }
    }

    private void getStatus() {
        IKeyManager keyManager = KeyManager.getInstance();
        //keyManager.getValue(KeyTools.createKey(FlightControllerKey.Status));
    }
    private void gimbalPoseBody() {
        // Get the Gimbal instance (assuming 0 is the main forward gimbal)
        IKeyManager keyManager = KeyManager.getInstance();
        Attitude gimbal = keyManager.getValue(KeyTools.createKey(GimbalKey.KeyGimbalAttitude));

        // Find the TextView to display the gimbal pose
        TextView textView = findViewById(R.id.main_text);

        if (gimbal != null) {
            // Retrieve yaw, pitch, and roll relative to the drone's body frame
            double yaw = gimbal.getYaw();
            double pitch = gimbal.getPitch();
            double roll = gimbal.getRoll();

            // Set the values on the TextView
            String gimbalPoseText = String.format("Yaw: %.2f°\nPitch: %.2f°\nRoll: %.2f°", yaw, pitch, roll);
            textView.setText(gimbalPoseText);

            // Log for debugging purposes
            Log.i("GimbalPose", gimbalPoseText);
        } else {
            // If the gimbal is unavailable, display a warning message on the TextView
            textView.setText("Gimbal not available");
            Log.w("GimbalPose", "Gimbal not found or not available.");
        }
    }

    private void startTakeoff() {
        IKeyManager keyManager = KeyManager.getInstance();
        keyManager.performAction(KeyTools.createKey(FlightControllerKey.KeyStartTakeoff), null);
        Log.i("MyApp", "Drone takeoff initiated");
    }

    private void startLanding() {
        IKeyManager keyManager = KeyManager.getInstance();
        keyManager.performAction(KeyTools.createKey(FlightControllerKey.KeyStartAutoLanding), null);
        Log.i("MyApp", "Drone takeoff initiated");
    }

    private void getType() {
        IKeyManager keyType = KeyManager.getInstance();
        ProductType typeValue = keyType.getValue(KeyTools.createKey(ProductKey.KeyProductType));
        TextView textView = findViewById(R.id.main_text);
        textView.setText("Name: " + typeValue);
        Log.i("MyApp", "Sent name");
    }

    private void setHomeCurrentLocation(){
        IKeyManager keyManager = KeyManager.getInstance();
        keyManager.performAction(KeyTools.createKey(FlightControllerKey.KeySetHomeLocationUsingAircraftCurrentLocation), null);
    }

    /*// New method to set the drone's global position
    private void setGlobalPosition(double latitude, double longitude) {
        // Use DJI SDK to set the global position (waypoint movement)
        IKeyManager keyManager = KeyManager.getInstance();

        LocationCoordinate2D targetLocation = new LocationCoordinate2D(latitude, longitude);
        // Assuming you want to set the global position with a waypoint
        DJIKey key = KeyTools.createKey(FlightControllerKey.KeyWaypoints);

        keyManager.setValue(key, targetLocation, null);
    }*/

    private void startGoHome(){
        IKeyManager keyManager = KeyManager.getInstance();
        keyManager.performAction(KeyTools.createKey(FlightControllerKey.KeyStartGoHome), null);
    }
}



