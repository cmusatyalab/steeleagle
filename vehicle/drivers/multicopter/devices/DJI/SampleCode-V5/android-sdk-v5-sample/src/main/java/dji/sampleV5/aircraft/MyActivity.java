package dji.sampleV5.aircraft;

import static dji.sdk.keyvalue.key.co_z.KeyCompassHeading;
import static dji.sdk.keyvalue.key.co_z.KeyGPSSatelliteCount;
import static dji.v5.manager.interfaces.ICameraStreamManager.FrameFormat.RGBA_8888;

import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.InputType;
import android.util.Log;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;

import java.io.ByteArrayOutputStream;
import java.io.File;

import dji.sdk.keyvalue.key.BatteryKey;
import dji.sdk.keyvalue.key.FlightControllerKey;
import dji.sdk.keyvalue.key.GimbalKey;
import dji.sdk.keyvalue.key.ProductKey;
import dji.sdk.keyvalue.value.camera.CameraMode;
import dji.sdk.keyvalue.value.common.Attitude;
import dji.sdk.keyvalue.value.common.ComponentIndexType;
import dji.sdk.keyvalue.value.common.LocationCoordinate2D;
import dji.sdk.keyvalue.value.common.LocationCoordinate3D;
import dji.sdk.keyvalue.value.common.Velocity3D;
import dji.sdk.keyvalue.value.flightcontroller.CompassCalibrationState;
import dji.sdk.keyvalue.value.flightcontroller.FlyToMode;
import dji.sdk.keyvalue.value.flightcontroller.GoHomeState;
import dji.sdk.keyvalue.value.product.ProductType;
import dji.v5.common.callback.CommonCallbacks;
import dji.v5.common.error.IDJIError;
import dji.v5.manager.KeyManager;
import dji.sdk.keyvalue.key.CameraKey;
import dji.sdk.keyvalue.key.KeyTools;
import dji.v5.manager.aircraft.waypoint3.WaypointMissionManager;
import dji.v5.manager.datacenter.camera.CameraStreamManager;
import dji.v5.manager.intelligent.IntelligentFlightManager;
import dji.v5.manager.intelligent.flyto.FlyToParam;
import dji.v5.manager.intelligent.flyto.FlyToTarget;
import dji.v5.manager.intelligent.flyto.IFlyToMissionManager;
import dji.v5.manager.interfaces.ICameraStreamManager;
import dji.v5.manager.interfaces.IKeyManager;
import dji.v5.manager.interfaces.IWaypointMissionManager;

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

        // Set start go home using current location button behavior
        Button startGoHomeAndHoverButton = findViewById(R.id.start_go_home_and_hover);
        startGoHomeAndHoverButton.setOnClickListener(v -> startGoHomeAndHover());

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

        // Start image preview button behavior
        Button startImagePreviewButton = findViewById(R.id.start_image_preview);
        startImagePreviewButton.setOnClickListener(v -> startCameraFramePreview());

        // Stop image preview button behavior
        Button stopImagePreviewButton = findViewById(R.id.stop_image_preview);
        stopImagePreviewButton.setOnClickListener(v -> stopCameraFramePreview());
    }
    //try to get home not to land, switch to haversine, also check for altitude, switch to waypoints api, get the set velocity functions, gimbal movement

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
        Double compassHeadingDegrees = keyManager.getValue(KeyTools.createKey(FlightControllerKey.KeyCompassHeading));

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

        // Also stop monitoring if in progress
        if (isGoingHomeAndHover) {
            isGoingHomeAndHover = false;
            if (homeCheckHandler != null && homeCheckRunnable != null) {
                homeCheckHandler.removeCallbacks(homeCheckRunnable);
            }
            Log.i("MyApp", "Stopped go home and monitoring");
        }
    }

    private Handler homeCheckHandler;
    private Runnable homeCheckRunnable;
    private boolean isGoingHomeAndHover = false;

    private void startGoHomeAndHover() {
        if (isGoingHomeAndHover) {
            Log.w("MyApp", "Go home and hover already in progress");
            return;
        }

        isGoingHomeAndHover = true;

        // Start the go home action
        IKeyManager keyManager = KeyManager.getInstance();
        keyManager.performAction(KeyTools.createKey(FlightControllerKey.KeyStartGoHome), null);

        // Start monitoring location
        startLocationMonitoring();

        Log.i("MyApp", "Started go home and hover");
    }

    private void startLocationMonitoring() {
        if (homeCheckHandler == null) {
            homeCheckHandler = new Handler(Looper.getMainLooper());
        }

        homeCheckRunnable = new Runnable() {
            @Override
            public void run() {
                if (!isGoingHomeAndHover) {
                    return; // Stop if process was cancelled
                }

                if (checkIfAtHomeLocation()) {
                    IKeyManager keyManager = KeyManager.getInstance();
                    // We've reached home location
                    // add the altitude check stuff here before calling stopgohome
                    Double currentAltitude = keyManager.getValue(KeyTools.createKey(FlightControllerKey.KeyAltitude));
                    Integer goHomeHeight = keyManager.getValue(KeyTools.createKey(FlightControllerKey.KeyGoHomeHeight));
                    if (Math.abs(currentAltitude - goHomeHeight) <= 1.0f) {
                        // Case 1: already at the correct altitude
                        stopGoHome();
                        isGoingHomeAndHover = false;
                        Log.i("MyApp", "Reached home location - stopping go home to hover");

                    } else if (currentAltitude < goHomeHeight) {
                        // Case 2: below go home height
                        // add code here
                            // Move 60 meters north (bearing 0 degrees)
                            double bearing = 0.0;
                            float distance = 60f; // meters

                            LocationCoordinate2D fakeHome = keyManager.getValue(KeyTools.createKey(FlightControllerKey.KeyHomeLocation));

                            double radiusEarth = 6371000.0; // meters
                            double angularDistance = distance / radiusEarth;

                            double lat1 = Math.toRadians(fakeHome.getLatitude());
                            double lon1 = Math.toRadians(fakeHome.getLongitude());

                            double lat2 = Math.asin(Math.sin(lat1) * Math.cos(angularDistance) +
                                    Math.cos(lat1) * Math.sin(angularDistance) * Math.cos(Math.toRadians(bearing)));

                            double lon2 = lon1 + Math.atan2(Math.sin(Math.toRadians(bearing)) * Math.sin(angularDistance) * Math.cos(lat1),
                                    Math.cos(angularDistance) - Math.sin(lat1) * Math.sin(lat2));

                            lat2 = Math.toDegrees(lat2);
                            lon2 = Math.toDegrees(lon2);

                            fakeHome = new LocationCoordinate2D(lat2, lon2);

                            keyManager.setValue(
                                    KeyTools.createKey(FlightControllerKey.KeyHomeLocation),
                                    fakeHome,
                                    null
                            );

                            Log.i("MyApp", "Set fake home point ~60m away to force climb");

                            // Begin monitoring climb
                            Handler climbHandler = new Handler(Looper.getMainLooper());
                            Runnable climbMonitor = new Runnable() {
                                @Override
                                public void run() {
                                    Double alt = keyManager.getValue(KeyTools.createKey(FlightControllerKey.KeyAltitude));
                                    if (alt != null && alt >= goHomeHeight - 0.5f) {
                                        stopGoHome();
                                        isGoingHomeAndHover = false;
                                        Log.i("MyApp", "Reached goHomeHeight on climb - stopping go home");
                                    } else {
                                        climbHandler.postDelayed(this, 200);
                                    }
                                }
                            };
                            climbHandler.post(climbMonitor);


                        Log.i("MyApp", "Below go home height - forcing climb with fake home");

                    } else {
                        // Case 3: above go home height
                        Log.i("MyApp", "Above go home height - waiting for descent");

                        // Begin monitoring descent
                        Handler descentHandler = new Handler(Looper.getMainLooper());
                        Runnable descentMonitor = new Runnable() {
                            @Override
                            public void run() {
                                Double alt = keyManager.getValue(KeyTools.createKey(FlightControllerKey.KeyAltitude));
                                if (alt != null && alt <= goHomeHeight + 0.5f) {
                                    stopGoHome();
                                    Log.i("MyApp", "Descending to goHomeHeight - stopping go home");
                                } else {
                                    descentHandler.postDelayed(this, 200);
                                }
                            }
                        };
                        descentHandler.post(descentMonitor);
                    }
                } else {
                    // Continue monitoring - check again in 500ms
                    homeCheckHandler.postDelayed(this, 200);
                }
            }
        };

        // Start the monitoring loop
        homeCheckHandler.post(homeCheckRunnable);
    }

    private boolean checkIfAtHomeLocation() {
        try {
            IKeyManager keyManager = KeyManager.getInstance();

            // Get current aircraft location
            LocationCoordinate2D currentLocation = keyManager.getValue(KeyTools.createKey(FlightControllerKey.KeyAircraftLocation));

            // Get home location
            LocationCoordinate2D homeLocation = keyManager.getValue(KeyTools.createKey(FlightControllerKey.KeyHomeLocation));

            if (currentLocation == null || homeLocation == null) {
                Log.w("MyApp", "Location data not available");
                return false;
            }

            double currentLat = Math.toRadians(currentLocation.getLatitude());
            double currentLon = Math.toRadians(currentLocation.getLongitude());
            double homeLat = Math.toRadians(homeLocation.getLatitude());
            double homeLon = Math.toRadians(homeLocation.getLongitude());

            // Haversine formula
            double dLat = homeLat - currentLat;
            double dLon = homeLon - currentLon;
            double a = Math.pow(Math.sin(dLat / 2), 2) +
                    Math.cos(currentLat) * Math.cos(homeLat) * Math.pow(Math.sin(dLon / 2), 2);
            double c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
            // Earth's radius in meters
            double distance = 6371000 * c;
            // Threshold
            boolean isAtHome = distance < 3;

            Log.d("MyApp", String.format("Distance to home: %.2f meters | At home: %b", distance, isAtHome));

            return isAtHome;

        } catch (Exception e) {
            Log.e("MyApp", "Error checking home location with Haversine: " + e.getMessage());
            return false;
        }
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        stopGoHome();
    }

    private void goHomeStatus() {
        IKeyManager keyType = KeyManager.getInstance();
        GoHomeState status = keyType.getValue(KeyTools.createKey(FlightControllerKey.KeyGoHomeStatus));
        TextView textView = findViewById(R.id.main_text);
        textView.setText("Status: " + status);
        Log.i("MyApp", "Sent go home status");
    }
    //end of of the set and go home functions

    private void waypoint(File kmzFile) {
        TextView textView = findViewById(R.id.main_text);
        if (kmzFile == null || !kmzFile.exists()) {
            //error case for the file being incorrect
            textView.setText("KMZ file not found.");
            Log.e("MyApp", "KMZ file is null or does not exist.");
        }
        IWaypointMissionManager waypointMissionManager = WaypointMissionManager.getInstance();
    }

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

    private void setGlobalPosition(double latitude, double longitude, double altitude, int flyingHeight) {
        Log.i("MyApp", "Start of the set global position function");
        //creating the target
        FlyToTarget flyToTarget = new FlyToTarget();
        flyToTarget.setTargetLocation(new LocationCoordinate3D(latitude, longitude, altitude));
        flyToTarget.setMaxSpeed(1);
        //creating the parameters
        FlyToParam flyParam = new FlyToParam();
        flyParam.setHeight(flyingHeight);
        flyParam.setFlyToMode(FlyToMode.SET_HEIGHT);
        //creating and executing the mission command to make the drone actually move to the coordinate
        IFlyToMissionManager flyToMissionManager = IntelligentFlightManager.getInstance().getFlyToMissionManager();
        Log.i("MyApp", "Start of mission itself");
        flyToMissionManager.startMission(flyToTarget, flyParam, new CommonCallbacks.CompletionCallback() {
            @Override
            public void onSuccess() {
                Log.i("MyApp", "FlyTo mission started successfully.");
            }

            @Override
            public void onFailure(@NonNull IDJIError idjiError) {
                Log.e("MyApp", "FlyTo mission failed: " + idjiError.description());
            }
        });
        Log.i("MyApp", "End of mission itself");
    }

    //code for camera image on screen
    class myFrameHandler_t implements ICameraStreamManager.CameraFrameListener, Runnable {

        Bitmap bitmap = null;
        long lastTime = 0;

        byte[] byteArray;

        public void onFrame(@NonNull byte[] frameData, int offset, int length, int width, int height, @NonNull ICameraStreamManager.FrameFormat format) {
            Log.i("MyApp", "Got onFrame");
            bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888);
            int[] colors = new int[width * height];
            Log.i("MyApp", "before for loop");
            for (int i = 0; i < width * height; i++) {
                colors[i] = Color.rgb(frameData[i * 4] & 0xFF, frameData[i * 4 + 1] & 0xFF, frameData[i * 4 + 2] & 0xFF);
            }
            Log.i("MyApp", "after for loop");
            bitmap.setPixels(colors, 0, width, 0, 0, width, height);

            //conversion to jpeg
            ByteArrayOutputStream stream = new ByteArrayOutputStream();
            bitmap.compress(Bitmap.CompressFormat.JPEG, 50, stream);
            byteArray = stream.toByteArray();
            runOnUiThread(this::run);
            Log.i("MyApp", "after display");
        }

        @Override
        public void run() {
            long millis = System.currentTimeMillis();
            float fps = 1000 / (millis - lastTime);
            lastTime = millis;
            TextView textView = findViewById(R.id.main_text);
            textView.setText("fps is: " + fps);
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

    //the remainder of this code is all android studio prompting code (not necessary for future implementation, just for current testing purposes)
    interface ValueCallback<T> {
        void onValue(T value);

        void onCancel();
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

                                intPrompt("Enter Flying height", new ValueCallback<Integer>() {
                                    @Override
                                    public void onValue(Integer flyingHeight) {
                                        Log.i("MyApp", "Flying Height: " + flyingHeight);

                                        // All inputs collected — call your function here
                                        setGlobalPosition(latitude, longitude, altitude, flyingHeight);
                                    }

                                    @Override
                                    public void onCancel() {
                                        Log.i("MyApp", "Flying height input cancelled");
                                    }
                                });
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