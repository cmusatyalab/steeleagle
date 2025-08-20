package dji.sampleV5.aircraft;


import static java.lang.Math.abs;
import static dji.sdk.keyvalue.key.co_z.KeyCompassHeading;
import static dji.sdk.keyvalue.key.co_z.KeyGPSSatelliteCount;
import static dji.v5.manager.interfaces.ICameraStreamManager.FrameFormat.RGBA_8888;

import android.Manifest;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.text.InputType;
import android.util.Log;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.FileReader;
import java.io.FileWriter;
import java.io.InputStream;
import java.util.Enumeration;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;
import java.util.zip.ZipOutputStream;

import dji.sdk.keyvalue.key.BatteryKey;
import dji.sdk.keyvalue.key.FlightControllerKey;
import dji.sdk.keyvalue.key.GimbalKey;
import dji.sdk.keyvalue.key.ProductKey;
import dji.sdk.keyvalue.value.camera.CameraMode;
import dji.sdk.keyvalue.value.common.Attitude;
import dji.sdk.keyvalue.value.common.ComponentIndexType;
import dji.sdk.keyvalue.value.common.LocationCoordinate2D;
import dji.sdk.keyvalue.value.common.Velocity3D;
import dji.sdk.keyvalue.value.flightcontroller.CompassCalibrationState;
import dji.sdk.keyvalue.value.flightcontroller.FlightCoordinateSystem;
import dji.sdk.keyvalue.value.flightcontroller.GoHomeState;
import dji.sdk.keyvalue.value.flightcontroller.RollPitchControlMode;
import dji.sdk.keyvalue.value.flightcontroller.VerticalControlMode;
import dji.sdk.keyvalue.value.flightcontroller.VirtualStickFlightControlParam;
import dji.sdk.keyvalue.value.flightcontroller.YawControlMode;
import dji.sdk.keyvalue.value.gimbal.CtrlInfo;
import dji.sdk.keyvalue.value.gimbal.GimbalSpeedRotation;
import dji.sdk.keyvalue.value.product.ProductType;
import dji.v5.common.callback.CommonCallbacks;
import dji.v5.common.error.IDJIError;
import dji.v5.manager.KeyManager;
import dji.sdk.keyvalue.key.CameraKey;
import dji.sdk.keyvalue.key.KeyTools;
import dji.v5.manager.aircraft.virtualstick.VirtualStickManager;
import dji.v5.manager.aircraft.waypoint3.WaypointMissionExecuteStateListener;
import dji.v5.manager.aircraft.waypoint3.WaypointMissionManager;
import dji.v5.manager.aircraft.waypoint3.model.WaypointMissionExecuteState;
import dji.v5.manager.datacenter.camera.CameraStreamManager;
import dji.v5.manager.interfaces.ICameraStreamManager;
import dji.v5.manager.interfaces.IKeyManager;


public class MyActivity extends AppCompatActivity implements WaypointMissionExecuteStateListener {

    private static final String TAG = "MyActivity";
    private static final int REQUEST_CODE_STORAGE_PERMISSION = 101;
    private double pendingLat = 0.0;
    private double pendingLon = 0.0;
    private double pendingAlt = 0;

    private WaypointMissionManager waypointManager = null;

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

        // Type button behavior
        Button typeButton = findViewById(R.id.type_button);
        typeButton.setOnClickListener(v -> getType());

        // Set home using current location button behavior
        Button currentLocationHomeButton = findViewById(R.id.set_home_current_location);
        currentLocationHomeButton.setOnClickListener(v -> setHomeCurrentLocation());

        // Set home using coordinates button behavior
        Button coordinatesHomeButton = findViewById(R.id.set_home_coordinates);
        coordinatesHomeButton.setOnClickListener(v -> setHomeUsingCoordinatesDialog());

        // Set home using coordinates button behavior
        Button setHomeHeightButton = findViewById(R.id.go_home_height);
        setHomeHeightButton.setOnClickListener(v -> setGoHomeHeightDialog());

        // Set start go home using current location button behavior
        Button startGoHomeAndLandButton = findViewById(R.id.start_go_home_and_land);
        startGoHomeAndLandButton.setOnClickListener(v -> startGoHomeAndLand());

        // Set stop go home using current location button behavior
        Button stopGoHomeButton = findViewById(R.id.stop_go_home);
        stopGoHomeButton.setOnClickListener(v -> stopGoHome());

        // Set go home status using current location button behavior
        Button goHomeStatusButton = findViewById(R.id.go_home_status);
        goHomeStatusButton.setOnClickListener(v -> goHomeStatus());

        // Is hovering status using current location button behavior
        Button isHoveringButton = findViewById(R.id.is_hovering);
        isHoveringButton.setOnClickListener(v -> isHovering());

        // Is hovering status using current location button behavior
        Button isHomeSet = findViewById(R.id.is_home_set);
        isHomeSet.setOnClickListener(v -> isHomeSet());

        // Is heading calibrated status using current location button behavior
        Button isHeadingCalibrated = findViewById(R.id.is_heading_calibrated);
        isHeadingCalibrated.setOnClickListener(v -> isHeadingCalibrated());

        // Start video button behavior
        Button startVideo = findViewById(R.id.start_video);
        startVideo.setOnClickListener(v -> startVideoRecording());

        // Stop video button behavior
        Button stopVideo = findViewById(R.id.stop_video);
        stopVideo.setOnClickListener(v -> stopVideoRecording());

        // Set global position button behavior
        Button setGlobalPositionButton = findViewById(R.id.set_global_position);
        setGlobalPositionButton.setOnClickListener(v -> setGlobalPositionDialog());

        // Start go to global position button behavior
        Button startGoToGlobalPositionButton = findViewById(R.id.start_go_to_global_position);
        startGoToGlobalPositionButton.setOnClickListener(v -> startWaypointMission());

        // Stop go to global position button behavior
        Button stopGoToGlobalPositionButton = findViewById(R.id.stop_go_to_global_position);
        stopGoToGlobalPositionButton.setOnClickListener(v -> stopWaypointMission());

        // Pause go to global position button behavior
        Button pauseGoToGlobalPositionButton = findViewById(R.id.pause_go_to_global_position);
        pauseGoToGlobalPositionButton.setOnClickListener(v -> pauseWaypointMission());

        // Resume go to global position button behavior
        Button resumeGoToGlobalPositionButton = findViewById(R.id.resume_go_to_global_position);
        resumeGoToGlobalPositionButton.setOnClickListener(v -> resumeWaypointMission());

        // Start image preview button behavior
        Button startImagePreviewButton = findViewById(R.id.start_image_preview);
        startImagePreviewButton.setOnClickListener(v -> startCameraFramePreview());

        // Stop image preview button behavior
        Button stopImagePreviewButton = findViewById(R.id.stop_image_preview);
        stopImagePreviewButton.setOnClickListener(v -> stopCameraFramePreview());

        // Set gimbal position
        Button setGimbalPoseButton = findViewById(R.id.set_gimbal_pose);
        setGimbalPoseButton.setOnClickListener(v -> setGimbalPoseDialog());

        // Set gimbal position
        Button startVelocityMovement = findViewById(R.id.start_velocity_movement);
        startVelocityMovement.setOnClickListener(v -> startVelocityMovementDialog());

        Button stopVelocityMovement = findViewById(R.id.stop_velocity_movement);
        stopVelocityMovement.setOnClickListener(v -> stopDroneVelocity());

        waypointManager = WaypointMissionManager.getInstance();
        waypointManager.addWaypointMissionExecuteStateListener(this);
    }
    //try to get home not to land, switch to haversine, also check for altitude, switch to waypoints api, get the set velocity functions, gimbal movement

    protected void onActivityResult(int requestCode, int resultCode, @Nullable Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == REQUEST_CODE_STORAGE_PERMISSION) {
            if (hasStoragePermission()) {
                waypoint(pendingLat, pendingLon, pendingAlt);
            } else {
                TextView textView = findViewById(R.id.main_text);
                textView.setText("Permission denied. Cannot edit KMZ.");
            }
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, @NonNull String[] permissions, @NonNull int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == REQUEST_CODE_STORAGE_PERMISSION) {
            boolean allGranted = true;
            for (int result : grantResults) {
                if (result != PackageManager.PERMISSION_GRANTED) {
                    allGranted = false;
                    break;
                }
            }

            if (allGranted) {
                waypoint(pendingLat, pendingLon, pendingAlt);
            } else {
                TextView textView = findViewById(R.id.main_text);
                textView.setText("Permission denied. Cannot edit KMZ.");
            }
        }
    }

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

        // Retrieve velocity in ENU coordinates
        Velocity3D enuVelocity = keyManager.getValue(KeyTools.createKey(FlightControllerKey.KeyAircraftVelocity));

        // Retrieve compass heading
        Double compassHeadingDegrees = keyManager.getValue(KeyTools.createKey(KeyCompassHeading));

        TextView statusTextView = findViewById(R.id.main_text);

        if (enuVelocity != null && compassHeadingDegrees != null) {
            // Extract components from ENU and convert to NED
            double velocityNorth = enuVelocity.getX();            // X -> North
            double velocityEast = enuVelocity.getY();             // Y -> East
            double velocityUp = -enuVelocity.getZ();              // Flip Z for ENU to NED

            // Horizontal velocity vector (North, East)
            double[] horizontalVelocityVector = {velocityNorth, velocityEast};

            // Calculate heading + 90 degrees (to align with aircraft's forward direction)
            double forwardHeadingDegrees = compassHeadingDegrees + 90.0;
            double forwardHeadingRadians = Math.toRadians(forwardHeadingDegrees);

            // Unit vector pointing forward in horizontal plane
            double forwardUnitX = Math.cos(forwardHeadingRadians);
            double forwardUnitY = Math.sin(forwardHeadingRadians);
            double[] forwardUnitVector = {forwardUnitX, forwardUnitY};

            // Calculate rightward heading (forward + 90 degrees)
            double rightHeadingRadians = Math.toRadians(forwardHeadingDegrees + 90.0);
            double rightUnitX = Math.cos(rightHeadingRadians);
            double rightUnitY = Math.sin(rightHeadingRadians);
            double[] rightUnitVector = {rightUnitX, rightUnitY};

            // Project velocity onto forward and right vectors (dot product)
            double forwardVelocity = -(horizontalVelocityVector[0] * forwardUnitVector[0]
                    + horizontalVelocityVector[1] * forwardUnitVector[1]);

            double rightVelocity = -(horizontalVelocityVector[0] * rightUnitVector[0]
                    + horizontalVelocityVector[1] * rightUnitVector[1]);

            // Display results
            String velocityText = String.format("Forward: %.2f, Right: %.2f, Up: %.2f", forwardVelocity, rightVelocity, velocityUp);
            statusTextView.setText(velocityText);
            Log.i("VelocityBody", velocityText);
        } else {
            statusTextView.setText("Velocity or Heading not available");
            Log.w("VelocityBody", "Velocity or Heading not available");
        }
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

    //start of of the set and go home functions
    private void setHomeCurrentLocation() {
        IKeyManager keyManager = KeyManager.getInstance();
        keyManager.performAction(KeyTools.createKey(FlightControllerKey.KeySetHomeLocationUsingAircraftCurrentLocation), null);
    }

    private void setHomeUsingCoordinates(double lat, double lon) {
        IKeyManager keyManager = KeyManager.getInstance();
        keyManager.setValue(KeyTools.createKey(FlightControllerKey.KeyHomeLocation), new LocationCoordinate2D(lat, lon), null);
    }

    private void setGoHomeHeight(int alt) {
        //unit meter, related to the altitude when taking off
        //If the drone is more than 50 meters away, it climbs or descends to the set KeyGoHomeHeight before flying home and landing.
        //If it’s within 50 meters, it returns home at its current altitude and lands without changing height.
        //f the forward vision system isn’t working, the drone always moves to KeyGoHomeHeight first, then flies home and lands.
        IKeyManager keyManager = KeyManager.getInstance();
        keyManager.setValue(KeyTools.createKey(FlightControllerKey.KeyGoHomeHeight), alt, null);
    }

    private void startGoHomeAndLand() {
        IKeyManager keyManager = KeyManager.getInstance();
        keyManager.performAction(KeyTools.createKey(FlightControllerKey.KeyStartGoHome), null);
    }

    private void stopGoHome() {
        IKeyManager keyManager = KeyManager.getInstance();
        keyManager.performAction(KeyTools.createKey(FlightControllerKey.KeyStopGoHome), null);
    }

    private void goHomeStatus() {
        IKeyManager keyType = KeyManager.getInstance();
        GoHomeState status = keyType.getValue(KeyTools.createKey(FlightControllerKey.KeyGoHomeStatus));
        TextView textView = findViewById(R.id.main_text);
        textView.setText("Status: " + status);
        Log.i("MyApp", "Sent go home status");
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        IKeyManager keyManager = KeyManager.getInstance();
        keyManager.cancelListen(this);
        stopGoHome();
    }
    //end of of the set and go home functions

    //start of waypoint code
    private boolean missionCompleted = false;
    private Handler mainHandler = new Handler(Looper.getMainLooper());

    @Override
    public void onMissionStateUpdate(WaypointMissionExecuteState missionState) {
        TextView textView = findViewById(R.id.main_text);
        Log.i("MyApp", "Mission State: " + missionState);
        textView.setText("Mission State: " + missionState);

        // Handle mission states to prevent auto RTH
        switch (missionState) {
            case IDLE:
                Log.i("MyApp", "Mission idle");
                break;

            case NOT_SUPPORTED:
                Log.e("MyApp", "Waypoint mission not supported");
                textView.setText("Waypoint mission not supported");
                break;

            case READY:
                missionCompleted = false;
                Log.i("MyApp", "Mission ready");
                break;

            case UPLOADING:
                Log.i("MyApp", "KMZ uploading");
                break;

            case PREPARING:
                Log.i("MyApp", "Mission preparing");
                break;

            case ENTER_WAYLINE:
                Log.i("MyApp", "Entering wayline - going to first waypoint");
                break;

            case EXECUTING:
                Log.i("MyApp", "Mission executing");
                break;

            case INTERRUPTED:
                Log.i("MyApp", "Mission interrupted");
                missionCompleted = false;
                break;

            case RECOVERING:
                Log.i("MyApp", "Mission recovering");
                break;

            case FINISHED:
                if (!missionCompleted) {
                    missionCompleted = true;
                    Log.i("MyApp", "Mission finished - preventing auto RTH");
                    textView.setText("Mission finished - hovering at destination");

                    // Cancel any pending RTH since mission is already finished
                    mainHandler.post(() -> {
                        cancelAnyReturnToHome();
                    });
                }
                break;
        }
    }

    private void cancelAnyReturnToHome() {
        IKeyManager keyManager = KeyManager.getInstance();
        keyManager.performAction(KeyTools.createKey(FlightControllerKey.KeyStopGoHome), null);
    }

    private void waypoint(double lat, double lon, double alt) {
        TextView textView = findViewById(R.id.main_text);
        Log.i("MyApp", "Lon: " + lon + " Lat: " + lat + " Alt: " + alt);
        File originalKmz = new File("/storage/emulated/0/DJI/mission.kmz");

        if (!originalKmz.exists()) {
            textView.setText("KMZ file not found.");
            Log.e("MyApp", "KMZ file not found.");
            return;
        }

        File tempDir = new File(getCacheDir(), "kmz_edit");
        File waylinesFile = new File(tempDir, "wpmz/waylines.wpml");

        File updatedKmz = null;
        try {
            // Step 1: Extract waylines.wpml and template.kml
            if (tempDir.exists()) deleteRecursive(tempDir);
            tempDir.mkdirs();

            ZipFile zipFile = new ZipFile(originalKmz);
            Enumeration<? extends ZipEntry> entries = zipFile.entries();

            boolean foundWaylines = false;
            boolean foundTemplate = false;

            while (entries.hasMoreElements()) {
                ZipEntry entry = entries.nextElement();
                String entryName = entry.getName();

                if (entryName.equalsIgnoreCase("wpmz/waylines.wpml") || entryName.equalsIgnoreCase("wpmz/template.kml")) {
                    File outFile = new File(tempDir, entryName);
                    outFile.getParentFile().mkdirs();

                    InputStream in = zipFile.getInputStream(entry);
                    FileOutputStream out = new FileOutputStream(outFile);

                    byte[] buffer = new byte[1024];
                    int len;
                    while ((len = in.read(buffer)) > 0) {
                        out.write(buffer, 0, len);
                    }

                    in.close();
                    out.close();

                    if (entryName.equalsIgnoreCase("wpmz/waylines.wpml")) foundWaylines = true;
                    if (entryName.equalsIgnoreCase("wpmz/template.kml")) foundTemplate = true;
                }
            }

            zipFile.close();

            if (!foundWaylines) {
                textView.setText("waylines.wpml not found in KMZ.");
                Log.e("MyApp", "waylines.wpml missing.");
                return;
            }

            if (!foundTemplate) {
                textView.setText("template.kml not found in KMZ.");
                Log.e("MyApp", "template.kml missing.");
                return;
            }

            // Step 2: Modify waylines.wpml
            StringBuilder contentBuilder = new StringBuilder();
            BufferedReader reader = new BufferedReader(new FileReader(waylinesFile));
            String line;
            while ((line = reader.readLine()) != null) {
                contentBuilder.append(line).append("\n");
            }
            reader.close();

            String wpmlContent = contentBuilder.toString();

            // Replace first and second <coordinates> blocks
            Pattern pattern = Pattern.compile("<coordinates>\\s*([-\\d.]+),([-\\d.]+)\\s*</coordinates>");
            Matcher matcher = pattern.matcher(wpmlContent);

            StringBuffer sb = new StringBuffer();
            int coordIndex = 0;

            // Getting the current location for the first coordinate in the mission
            IKeyManager keyManager = KeyManager.getInstance();
            LocationCoordinate2D gpsLocation = keyManager.getValue(KeyTools.createKey(FlightControllerKey.KeyAircraftLocation));
            double currentLat = 999;
            double currentLon = 999;
            if (gpsLocation != null) {
                currentLat = gpsLocation.getLatitude();
                currentLon = gpsLocation.getLongitude();
            } else {
                textView.setText("GPS data not available");
                Log.w("MyApp", "GPS location is null");
            }

            while (matcher.find()) {
                String replacement;
                if (coordIndex == 0) {
                    replacement = "<coordinates>\n            " + currentLon + "," + currentLat + "\n          </coordinates>";
                } else if (coordIndex == 1) {
                    replacement = "<coordinates>\n            " + lon + "," + lat + "\n          </coordinates>";
                } else {
                    continue;
                }
                matcher.appendReplacement(sb, Matcher.quoteReplacement(replacement));
                coordIndex++;
            }
            matcher.appendTail(sb);

            Pattern altitudePattern = Pattern.compile("<wpml:executeHeight>([^<]*)</wpml:executeHeight>");
            Matcher altitudeMatcher = altitudePattern.matcher(sb.toString());
            StringBuffer sb2 = new StringBuffer();
            int altitudeIndex = 0;

            while (altitudeMatcher.find()) {
                String replacement;
                if (altitudeIndex == 0) {
                    replacement = "<wpml:executeHeight>" + alt + "</wpml:executeHeight>";
                } else if (altitudeIndex == 1) {
                    replacement = "<wpml:executeHeight>" + alt + "</wpml:executeHeight>";
                } else {
                    continue;
                }
                altitudeMatcher.appendReplacement(sb2, Matcher.quoteReplacement(replacement));
                altitudeIndex++;
            }
            altitudeMatcher.appendTail(sb2);

            // Write back the updated XML
            BufferedWriter writer = new BufferedWriter(new FileWriter(waylinesFile));
            writer.write(sb2.toString());
            writer.close();

            // Step 3: Repack only waylines.wpml and template.kml into a new KMZ
            updatedKmz = new File("/storage/emulated/0/DJI/mission_updated.kmz");
            FileOutputStream fos = new FileOutputStream(updatedKmz);
            ZipOutputStream zos = new ZipOutputStream(fos);

            addToZip(tempDir, tempDir, zos);

            zos.close();
            fos.close();

            textView.setText("KMZ updated successfully.");
            Log.i("MyApp", "KMZ updated: " + updatedKmz.getAbsolutePath());

        } catch (Exception e) {
            textView.setText("Error updating KMZ.");
            Log.e("MyApp", "Exception during KMZ edit", e);
        }
        waypointManager.pushKMZFileToAircraft(updatedKmz.getPath(), null);
        Log.i("MyApp", "doneeeeeee");
    }

    // Recursively add files to ZipOutputStream
    private void addToZip(File rootDir, File sourceFile, ZipOutputStream zos) throws Exception {
        if (sourceFile.isDirectory()) {
            for (File file : sourceFile.listFiles()) {
                addToZip(rootDir, file, zos);
            }
        } else {
            String zipEntryName = rootDir.toURI().relativize(sourceFile.toURI()).getPath();
            ZipEntry zipEntry = new ZipEntry(zipEntryName);
            zos.putNextEntry(zipEntry);

            FileInputStream fis = new FileInputStream(sourceFile);
            byte[] buffer = new byte[1024];
            int len;
            while ((len = fis.read(buffer)) > 0) {
                zos.write(buffer, 0, len);
            }

            zos.closeEntry();
            fis.close();
        }
    }

    // Helper to recursively delete folders
    private void deleteRecursive(File fileOrDirectory) {
        if (fileOrDirectory.isDirectory()) {
            for (File child : fileOrDirectory.listFiles()) {
                deleteRecursive(child);
            }
        }
        fileOrDirectory.delete();
    }

    private boolean hasStoragePermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            return Environment.isExternalStorageManager();
        } else {
            return ContextCompat.checkSelfPermission(this, Manifest.permission.READ_EXTERNAL_STORAGE) == PackageManager.PERMISSION_GRANTED &&
                    ContextCompat.checkSelfPermission(this, Manifest.permission.WRITE_EXTERNAL_STORAGE) == PackageManager.PERMISSION_GRANTED;
        }
    }

    private void requestStoragePermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            try {
                Intent intent = new Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION);
                intent.setData(Uri.parse("package:" + getPackageName()));
                startActivityForResult(intent, REQUEST_CODE_STORAGE_PERMISSION);
            } catch (Exception e) {
                Intent intent = new Intent(Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION);
                startActivityForResult(intent, REQUEST_CODE_STORAGE_PERMISSION);
            }
        } else {
            ActivityCompat.requestPermissions(
                    this,
                    new String[]{Manifest.permission.READ_EXTERNAL_STORAGE, Manifest.permission.WRITE_EXTERNAL_STORAGE},
                    REQUEST_CODE_STORAGE_PERMISSION
            );
        }
    }

    private void startWaypointMission() {
        TextView textView = findViewById(R.id.main_text);
        waypointManager.startMission("mission_updated", new CommonCallbacks.CompletionCallback() {
            @Override
            public void onSuccess() {
                Log.i("MyApp", "Waypoint mission started successfully.");
                //textView.setText("Mission started");
            }

            @Override
            public void onFailure(@NonNull IDJIError idjiError) {
                Log.i("MyApp", "Mission failed: " + idjiError.description());
                textView.setText("Mission failed: " + idjiError.description());
            }
        });
    }

    private void stopWaypointMission() {
        TextView textView = findViewById(R.id.main_text);
        waypointManager.stopMission("mission_updated", new CommonCallbacks.CompletionCallback() {
            @Override
            public void onSuccess() {
                Log.i("MyApp", "Waypoint mission stopped successfully.");
                //textView.setText("Mission stopped");
            }

            @Override
            public void onFailure(@NonNull IDJIError idjiError) {
                Log.i("MyApp", "Failed to stop mission: " + idjiError.description());
                textView.setText("Failed to stop mission: " + idjiError.description());
            }
        });
    }

    private void pauseWaypointMission() {
        TextView textView = findViewById(R.id.main_text);
        waypointManager.pauseMission(new CommonCallbacks.CompletionCallback() {
            @Override
            public void onSuccess() {
                Log.i("MyApp", "Waypoint mission paused successfully.");
                //textView.setText("Mission paused");
            }

            @Override
            public void onFailure(@NonNull IDJIError idjiError) {
                Log.i("MyApp", "Failed to pause mission: " + idjiError.description());
                textView.setText("Failed to pause mission: " + idjiError.description());
            }
        });
    }

    private void resumeWaypointMission() {
        TextView textView = findViewById(R.id.main_text);
        waypointManager.resumeMission(new CommonCallbacks.CompletionCallback() {
            @Override
            public void onSuccess() {
                Log.i("MyApp", "Waypoint mission resumed successfully.");
                //textView.setText("Mission resumed");
            }

            @Override
            public void onFailure(@NonNull IDJIError idjiError) {
                Log.i("MyApp", "Failed to resume mission: " + idjiError.description());
                textView.setText("Failed to resume mission: " + idjiError.description());
            }
        });
    }
    //end of waypoint code

    private void isHovering() {
        IKeyManager keyManager = KeyManager.getInstance();
        TextView textView = findViewById(R.id.main_text);
        Boolean hover = keyManager.getValue(KeyTools.createKey(FlightControllerKey.KeyIsAircraftHovering));
        textView.setText("isHovering: " + hover);
        Log.i("MyApp", "isHovering value sent");
    }

    private void isHomeSet() {
        IKeyManager keyManager = KeyManager.getInstance();
        TextView textView = findViewById(R.id.main_text);
        Boolean home = keyManager.getValue(KeyTools.createKey(FlightControllerKey.KeyIsHomeLocationSet));
        textView.setText("isHomeSet: " + home);
        Log.i("MyApp", "isHomeSet value sent");
    }

    private void isHeadingCalibrated() {
        IKeyManager keyManager = KeyManager.getInstance();
        TextView textView = findViewById(R.id.main_text);
        Boolean home = keyManager.getValue(KeyTools.createKey(FlightControllerKey.KeyIsHeadingCalibrated));
        textView.setText("isHeadingCalibrated: " + home);
        Log.i("MyApp", "isHeadingCalibrated value sent");
    }

    private void startVideoRecording() {
        IKeyManager keyManager = KeyManager.getInstance();
        // Set camera mode to video
        keyManager.setValue(KeyTools.createKey(CameraKey.KeyCameraMode), CameraMode.VIDEO_NORMAL, null);
        keyManager.performAction(KeyTools.createKey(CameraKey.KeyStartRecord), null);
        Log.i("MyApp", "Starting video");
    }

    private void stopVideoRecording() {
        IKeyManager keyManager = KeyManager.getInstance();
        // Set camera mode to video
        keyManager.setValue(KeyTools.createKey(CameraKey.KeyCameraMode), CameraMode.VIDEO_NORMAL, null);
        keyManager.performAction(KeyTools.createKey(CameraKey.KeyStopRecord), null);
        Log.i("MyApp", "Stopped Video");
    }

    //code for camera image on screen
    class myFrameHandler_t implements ICameraStreamManager.CameraFrameListener, Runnable {
        Bitmap bitmap = null;
        long lastTime = 0;
        byte[] byteArray;

        public void onFrame(@NonNull byte[] frameData, int offset, int length, int width, int height, @NonNull ICameraStreamManager.FrameFormat format) {
            //Log.i("MyApp", "Got onFrame");
            bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888);
            int[] colors = new int[width * height];
            //Log.i("MyApp", "before for loop");
            for (int i = 0; i < width * height; i++) {
                colors[i] = Color.rgb(frameData[i * 4] & 0xFF, frameData[i * 4 + 1] & 0xFF, frameData[i * 4 + 2] & 0xFF);
            }
            //Log.i("MyApp", "after for loop");
            bitmap.setPixels(colors, 0, width, 0, 0, width, height);

            //conversion to jpeg
            ByteArrayOutputStream stream = new ByteArrayOutputStream();
            bitmap.compress(Bitmap.CompressFormat.JPEG, 50, stream);
            byteArray = stream.toByteArray();
            runOnUiThread(this::run);
            //Log.i("MyApp", "after display");
        }

        @Override
        public void run() {
            long millis = System.currentTimeMillis();
            float fps = 1000 / (millis - lastTime);
            lastTime = millis;
            TextView textView = findViewById(R.id.main_text);
            //textView.setText("fps is: " + fps);
            ImageView imageView = findViewById(R.id.my_image_view);
            //imageView.setImageBitmap(bitmap);
            Bitmap bitmap = BitmapFactory.decodeByteArray(byteArray, 0, byteArray.length);
            imageView.setImageBitmap(bitmap);
        }
    }

    myFrameHandler_t myFrameHandler = new myFrameHandler_t();

    private void startCameraFramePreview() {
        ICameraStreamManager cameraStreamManager = CameraStreamManager.getInstance();
        cameraStreamManager.addFrameListener(
                ComponentIndexType.LEFT_OR_MAIN,
                RGBA_8888,
                myFrameHandler
        );
    }

    private void stopCameraFramePreview() {
        ICameraStreamManager cameraStreamManager = CameraStreamManager.getInstance();
        cameraStreamManager.removeFrameListener(myFrameHandler);
    }
    //end code for camera on screen

    //start of set gimbal related code
    private Handler gimbalHandler = new Handler(Looper.getMainLooper());
    private boolean isAdjustingGimbal = false;
    private final int gimbalIntervalMs = 10; // How often to update
    private final long maxGimbalDurationMs = 60_000; // Max adjustment duration = 30 seconds
    private long gimbalStartTimeMs;

    private void setGimbalPose(double targetYaw, double targetPitch, double targetRoll) {
        isAdjustingGimbal = true;
        gimbalStartTimeMs = System.currentTimeMillis(); // Mark start time

        Runnable gimbalRunnable = new Runnable() {
            @Override
            public void run() {
                if (!isAdjustingGimbal) return;

                long elapsedTime = System.currentTimeMillis() - gimbalStartTimeMs;
                if (elapsedTime > maxGimbalDurationMs) {
                    Log.w("Gimbal", "Gimbal adjustment timed out after 30 seconds.");
                    stopGimbalAdjustment(); // Stop loop
                    return;
                }

                IKeyManager keyManager = KeyManager.getInstance();
                Attitude gimbalTelemetry = keyManager.getValue(KeyTools.createKey(GimbalKey.KeyGimbalAttitude, 0));

                if (gimbalTelemetry == null) {
                    Log.e("Gimbal", "Failed to retrieve gimbal attitude");
                    return;
                }

                double currentYaw = gimbalTelemetry.getYaw();
                double currentPitch = gimbalTelemetry.getPitch();
                double currentRoll = gimbalTelemetry.getRoll();

                double differenceYaw = Math.abs(targetYaw - currentYaw);
                double differencePitch = Math.abs(targetPitch - currentPitch);
                double differenceRoll = Math.abs(targetRoll - currentRoll);

                double yawSpeed = 0;
                double pitchSpeed = 0;
                double rollSpeed = 0;

                if (differenceYaw > 1) {
                    yawSpeed = (currentYaw > targetYaw) ? -20 : 20;
                }
                if (differencePitch > 1) {
                    pitchSpeed = (currentPitch > targetPitch) ? -10 : 10;
                }
                if (differenceRoll > 0.1) {
                    rollSpeed = (currentRoll > targetRoll) ? -5 : 5;
                }

                if (differenceYaw > 3 || differencePitch > 3 || differenceRoll > 0.5) {
                    GimbalSpeedRotation rotation = new GimbalSpeedRotation(
                            pitchSpeed,
                            yawSpeed,
                            rollSpeed,
                            new CtrlInfo()
                    );
                    keyManager.performAction(
                            KeyTools.createKey(GimbalKey.KeyRotateBySpeed, 0),
                            rotation,
                            null
                    );

                    gimbalHandler.postDelayed(this, gimbalIntervalMs); // Loop again
                } else {
                    // Target reached — stop all movement
                    GimbalSpeedRotation stop = new GimbalSpeedRotation(0.0, 0.0, 0.0, new CtrlInfo());
                    keyManager.performAction(
                            KeyTools.createKey(GimbalKey.KeyRotateBySpeed, 0),
                            stop,
                            null
                    );
                    Log.i("Gimbal", "Target reached.");
                    stopGimbalAdjustment();
                }
            }
        };

        gimbalHandler.post(gimbalRunnable); // Start loop
    }

    public void stopGimbalAdjustment() {
        isAdjustingGimbal = false;
        gimbalHandler.removeCallbacksAndMessages(null);
    }
    //end of set gimbal pose code

    //start set velocity code
    private boolean isAdjustingDrone = false;
    private Handler droneHandler = new Handler(Looper.getMainLooper());
    private long droneStartTimeMs;
    private final long maxDroneDurationMs = 1200000; //120 sec time limit for testing   now, remove/edit this later for longer missions/commands
    private final int droneIntervalMs = 10;

    private void startDroneVelocityMovement(double targetForwardVelocity, double targetRightVelocity, double targetUpVelocity) {
        // First, enable virtual stick mode before starting velocity control
        VirtualStickManager.getInstance().enableVirtualStick(new CommonCallbacks.CompletionCallback() {
            @Override
            public void onSuccess() {
                VirtualStickManager.getInstance().setVirtualStickAdvancedModeEnabled(true);
                Log.i("VirtualStick", "Virtual stick advanced mode enabled");
                // Now start the actual velocity control loop
                startVelocityControlLoop(targetForwardVelocity, targetRightVelocity, targetUpVelocity);
            }

            @Override
            public void onFailure(@NonNull IDJIError error) {
                Log.e("MyApp", "Failed to enable virtual stick: " + error.description());
                isAdjustingDrone = false;
            }
        });
    }

    private void startVelocityControlLoop(double targetForwardVelocity, double targetRightVelocity, double targetUpVelocity) {
        isAdjustingDrone = true;
        droneStartTimeMs = System.currentTimeMillis(); // Mark start time
        TextView textView = findViewById(R.id.main_text);

        Runnable droneRunnable = new Runnable() {
            @Override
            public void run() {
                if (!isAdjustingDrone) return;

                // Timeout check (similar to gimbal)
                long elapsedTime = System.currentTimeMillis() - droneStartTimeMs;
                if (elapsedTime > maxDroneDurationMs) {
                    Log.w("MyApp", "Drone velocity adjustment timed out");
                    stopDroneVelocity();
                    return;
                }

                IKeyManager keyManager = KeyManager.getInstance();
                Velocity3D enuVelocity = keyManager.getValue(KeyTools.createKey(FlightControllerKey.KeyAircraftVelocity));
                Double compassHeadingDegrees = keyManager.getValue(KeyTools.createKey(KeyCompassHeading));

                if (enuVelocity == null || compassHeadingDegrees == null) {
                    Log.e("MyApp", "Failed to retrieve drone telemetry");
                    droneHandler.postDelayed(this, droneIntervalMs);
                    return;
                }

                // Extract components from ENU and convert to FRU
                double velocityNorth = enuVelocity.getX();
                double velocityEast = enuVelocity.getY();
                double velocityUp = -enuVelocity.getZ();

                double[] horizontalVelocityVector = {velocityNorth, velocityEast};

                double forwardHeadingDegrees = compassHeadingDegrees + 90.0;
                double forwardHeadingRadians = Math.toRadians(forwardHeadingDegrees);
                double forwardUnitX = Math.cos(forwardHeadingRadians);
                double forwardUnitY = Math.sin(forwardHeadingRadians);
                double[] forwardUnitVector = {forwardUnitX, forwardUnitY};

                double rightHeadingRadians = Math.toRadians(forwardHeadingDegrees + 90.0);
                double rightUnitX = Math.cos(rightHeadingRadians);
                double rightUnitY = Math.sin(rightHeadingRadians);
                double[] rightUnitVector = {rightUnitX, rightUnitY};

                double forwardVelocity = -(horizontalVelocityVector[0] * forwardUnitVector[0] +
                        horizontalVelocityVector[1] * forwardUnitVector[1]);
                double rightVelocity = -(horizontalVelocityVector[0] * rightUnitVector[0] +
                        horizontalVelocityVector[1] * rightUnitVector[1]);

                // Display results
                String velocityText = String.format("Forward: %.2f, Right: %.2f, Up: %.2f",
                        forwardVelocity, rightVelocity, velocityUp);
                textView.setText(velocityText);
                Log.i("MyApp", "Velocity: " + velocityText);

                double currentForward = forwardVelocity;
                double currentRight = rightVelocity;
                double currentUp = velocityUp;

                double differenceForward = Math.abs(targetForwardVelocity - currentForward);
                double differenceRight = Math.abs(targetRightVelocity - currentRight);
                double differenceUp = Math.abs(targetUpVelocity - currentUp);

                // Calculate virtual stick commands (similar to gimbal speed calculation)
                double pitchCommand = 0; // Forward/backward
                double rollCommand = 0;  // Left/right
                double throttleCommand = 0; // Up/down
                double yawCommand = 0;   // Keep current heading

                // Forward velocity control (pitch stick)
                if (differenceForward > 0.1) { // Tolerance similar to gimbal
                    if (currentForward < targetForwardVelocity) {
                        pitchCommand = calculateStickCommand(differenceForward, 0.5f); // Move forward
                    } else {
                        pitchCommand = -calculateStickCommand(differenceForward, 0.5f); // Move backward
                    }
                }

                // Right velocity control (roll stick)
                if (differenceRight > 0.1) {
                    if (currentRight < targetRightVelocity) {
                        rollCommand = calculateStickCommand(differenceRight, 0.5f); // Move right
                    } else {
                        rollCommand = -calculateStickCommand(differenceRight, 0.5f); // Move left
                    }
                }

                // Up velocity control (throttle stick)
                if (differenceUp > 0.1) {
                    if (currentUp < targetUpVelocity) {
                        throttleCommand = calculateStickCommand(differenceUp, 0.3f); // Move up
                    } else {
                        throttleCommand = -calculateStickCommand(differenceUp, 0.3f); // Move down
                    }
                }

                // Check if we've reached target (similar to gimbal target check)
                if (differenceForward <= 0.1 && differenceRight <= 0.1 && differenceUp <= 0.1) {
                    // Target reached - send zero commands to maintain position
                    VirtualStickFlightControlParam stickParam = new VirtualStickFlightControlParam();

                    // Configure control modes for velocity control
                    stickParam.setRollPitchCoordinateSystem(FlightCoordinateSystem.BODY);
                    stickParam.setVerticalControlMode(VerticalControlMode.VELOCITY);
                    stickParam.setYawControlMode(YawControlMode.ANGULAR_VELOCITY);
                    stickParam.setRollPitchControlMode(RollPitchControlMode.VELOCITY);

                    // FIXED: Swapped pitch and roll assignments
                    stickParam.setPitch(rollCommand);    // Roll command controls forward/backward
                    stickParam.setRoll(pitchCommand);    // Pitch command controls left/right
                    stickParam.setVerticalThrottle(0.0);
                    stickParam.setYaw(0.0);

                    VirtualStickManager.getInstance().sendVirtualStickAdvancedParam(stickParam);

                    Log.i("Drone", "Target velocity reached and maintaining");
                    // Continue looping to maintain velocity
                    droneHandler.postDelayed(this, droneIntervalMs);
                } else {
                    // Send virtual stick commands
                    VirtualStickFlightControlParam stickParam = new VirtualStickFlightControlParam();

                    // Configure control modes for velocity control
                    stickParam.setRollPitchCoordinateSystem(FlightCoordinateSystem.BODY);
                    stickParam.setVerticalControlMode(VerticalControlMode.VELOCITY);
                    stickParam.setYawControlMode(YawControlMode.ANGULAR_VELOCITY);
                    stickParam.setRollPitchControlMode(RollPitchControlMode.VELOCITY);

                    // FIXED: Swapped pitch and roll assignments
                    stickParam.setPitch(rollCommand);    // Roll command controls forward/backward
                    stickParam.setRoll(pitchCommand);    // Pitch command controls left/right
                    stickParam.setVerticalThrottle(throttleCommand);
                    stickParam.setYaw(yawCommand);

                    VirtualStickManager.getInstance().sendVirtualStickAdvancedParam(stickParam);

                    Log.d("Drone", String.format("Stick commands - Pitch: %.2f, Roll: %.2f, Throttle: %.2f",
                            rollCommand, pitchCommand, throttleCommand));

                    // Continue looping
                    droneHandler.postDelayed(this, droneIntervalMs);
                }
            }
        };

        droneHandler.post(droneRunnable); // Start loop
    }

    // Helper method to calculate stick command based on velocity difference
    private float calculateStickCommand(double velocityDifference, float maxCommand) {
        // Scale the command based on velocity difference (similar to gimbal speed scaling)
        float command = (float) Math.min(velocityDifference * 0.2, maxCommand); // Adjust scaling factor as needed
        return Math.max(command, 0.1f); // Minimum command to ensure movement
    }

    public void stopDroneVelocity() {
        isAdjustingDrone = false;
        droneHandler.removeCallbacksAndMessages(null);

        // Send zero commands to stop the drone
        VirtualStickFlightControlParam stopParam = new VirtualStickFlightControlParam();

        // Configure control modes
        stopParam.setRollPitchCoordinateSystem(FlightCoordinateSystem.BODY);
        stopParam.setVerticalControlMode(VerticalControlMode.VELOCITY);
        stopParam.setYawControlMode(YawControlMode.ANGULAR_VELOCITY);
        stopParam.setRollPitchControlMode(RollPitchControlMode.VELOCITY);

        stopParam.setPitch(0.0);
        stopParam.setRoll(0.0);
        stopParam.setVerticalThrottle(0.0);
        stopParam.setYaw(0.0);

        VirtualStickManager.getInstance().sendVirtualStickAdvancedParam(stopParam);

        // Disable virtual stick mode
        VirtualStickManager.getInstance().disableVirtualStick(new CommonCallbacks.CompletionCallback() {
            @Override
            public void onSuccess() {
                Log.i("MyApp", "Virtual stick disabled successfully");
            }

            @Override
            public void onFailure(@NonNull IDJIError error) {
                Log.e("MyApp", "Failed to disable virtual stick: " + error.description());
            }
        });

        Log.i("Drone", "Drone velocity control stopped");
    }
    //drone velocity ending
    //the remainder of this code is all android studio prompting code (not necessary for future implementation, just for current testing purposes)
    interface ValueCallback<T> {
        void onValue(T value);

        void onCancel();
    }

    private void setGimbalPoseDialog() {
        doublePrompt("Enter Yaw", new ValueCallback<Double>() {
            @Override
            public void onValue(Double yaw) {
                Log.i("MyApp", "Yaw: " + yaw);
                doublePrompt("Enter Pitch", new ValueCallback<Double>() {
                    @Override
                    public void onValue(Double pitch) {
                        Log.i("MyApp", "Pitch: " + pitch);
                        doublePrompt("Enter Roll", new ValueCallback<Double>() {
                            @Override
                            public void onValue(Double roll) {
                                Log.i("MyApp", "Roll: " + roll);

                                setGimbalPose(yaw, pitch, roll);
                            }

                            @Override
                            public void onCancel() {
                                Log.i("MyApp", "Longitude input cancelled");
                            }
                        });
                    }

                    @Override
                    public void onCancel() {
                        Log.i("MyApp", "Longitude input cancelled");
                    }
                });
            }

            @Override
            public void onCancel() {
                Log.i("MyApp", "Latitude input cancelled");
            }
        });
    }

    private void setGlobalPositionDialog() {
        doublePrompt("Enter Latitude", new ValueCallback<Double>() {
            @Override
            public void onValue(Double latitude) {
                Log.i("MyApp", "Latitude: " + latitude);

                doublePrompt("Enter Longitude", new ValueCallback<Double>() {
                    @Override
                    public void onValue(Double longitude) {
                        Log.i("MyApp", "Longitude: " + longitude);

                        doublePrompt("Enter Altitude", new ValueCallback<Double>() {
                            @Override
                            public void onValue(Double altitude) {
                                Log.i("MyApp", "Altitude: " + altitude);

                                // Call waypoint function
                                if (hasStoragePermission()) {
                                    waypoint(latitude, longitude, altitude);
                                } else {
                                    requestStoragePermission();
                                    Handler handler = new Handler();
                                    handler.postDelayed(new Runnable() {
                                        @Override
                                        public void run() {
                                            if (hasStoragePermission()) {
                                                waypoint(latitude, longitude, altitude);
                                            } else {
                                                Log.i("MyApp", "Still no permission after delay.");
                                            }
                                        }
                                    }, 5000); // 5-second delay
                                }
                            }

                            @Override
                            public void onCancel() {
                                Log.i("MyApp", "Altitude input cancelled");
                            }
                        });
                    }

                    @Override
                    public void onCancel() {
                        Log.i("MyApp", "Longitude input cancelled");
                    }
                });
            }

            @Override
            public void onCancel() {
                Log.i("MyApp", "Latitude input cancelled");
            }
        });
    }

    private void startVelocityMovementDialog() {
        doublePrompt("Enter Target Forward Velocity", new ValueCallback<Double>() {
            @Override
            public void onValue(Double forward_v) {
                Log.i("MyApp", "Forward Velocity: " + forward_v);

                doublePrompt("Enter Target Right Velocity", new ValueCallback<Double>() {
                    @Override
                    public void onValue(Double right_v) {
                        Log.i("MyApp", "Right Velocity: " + right_v);

                        doublePrompt("Enter Target Up Velocity", new ValueCallback<Double>() {
                            @Override
                            public void onValue(Double up_v) {
                                Log.i("MyApp", "Up Velocity: " + up_v);

                                // Call waypoint function
                                startDroneVelocityMovement(forward_v, right_v, up_v);

                            }

                            @Override
                            public void onCancel() {
                                Log.i("MyApp", "Altitude input cancelled");
                            }
                        });
                    }

                    @Override
                    public void onCancel() {
                        Log.i("MyApp", "Longitude input cancelled");
                    }
                });
            }

            @Override
            public void onCancel() {
                Log.i("MyApp", "Latitude input cancelled");
            }
        });
    }

    private void setHomeUsingCoordinatesDialog() {
        doublePrompt("Enter Latitude", new ValueCallback<Double>() {
            @Override
            public void onValue(Double latitude) {
                Log.i("MyApp", "Latitude: " + latitude);

                doublePrompt("Enter Longitude", new ValueCallback<Double>() {
                    @Override
                    public void onValue(Double longitude) {
                        Log.i("MyApp", "Longitude: " + longitude);
                        setHomeUsingCoordinates(latitude, longitude);
                    }

                    @Override
                    public void onCancel() {
                        Log.i("MyApp", "Longitude input cancelled");
                    }
                });
            }

            @Override
            public void onCancel() {
                Log.i("MyApp", "Latitude input cancelled");
            }
        });
    }

    private void setGoHomeHeightDialog() {
        intPrompt("Enter Altitude", new ValueCallback<Integer>() {
            @Override
            public void onValue(Integer altitude) {
                Log.i("MyApp", "Altitude: " + altitude);
                setGoHomeHeight(altitude);
            }

            @Override
            public void onCancel() {
                Log.i("MyApp", "Latitude input cancelled");
            }
        });
    }

    private void intPrompt(String message, ValueCallback<Integer> callback) {
        final EditText input = new EditText(this);
        input.setInputType(InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_FLAG_SIGNED);
        new AlertDialog.Builder(this)
                .setTitle(message)
                .setView(input)
                .setPositiveButton("Ok", (dialog, which) -> {
                    String text = input.getText().toString();
                    if (text.isEmpty()) {
                        callback.onCancel();
                        return;
                    }
                    try {
                        int height = Integer.parseInt(text);
                        callback.onValue(height);
                    } catch (NumberFormatException e) {
                        callback.onCancel();
                    }
                })
                .setNegativeButton("Cancel", (dialog, which) -> callback.onCancel())
                .show();
    }

    private void doublePrompt(String message, ValueCallback<Double> callback) {
        final EditText input = new EditText(this);
        input.setInputType(InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_FLAG_DECIMAL | InputType.TYPE_NUMBER_FLAG_SIGNED);
        new AlertDialog.Builder(this)
                .setTitle(message)
                .setView(input)
                .setPositiveButton("Ok", (dialog, which) -> {
                    String text = input.getText().toString();
                    if (text.isEmpty()) {
                        callback.onCancel();
                        return;
                    }
                    try {
                        double altitude = Double.parseDouble(text);
                        callback.onValue(altitude);
                    } catch (NumberFormatException e) {
                        callback.onCancel();
                    }
                })
                .setNegativeButton("Cancel", (dialog, which) -> callback.onCancel())
                .show();
    }
}