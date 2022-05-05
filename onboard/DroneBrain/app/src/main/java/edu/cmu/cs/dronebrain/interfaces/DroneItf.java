package edu.cmu.cs.dronebrain.interfaces;

public interface DroneItf {
    void connect();

    void takeoff();

    void land();

    void moveTo(double lat, double lng, double alt);

    void moveBy(double x, double y, double z);

    void rotateBy(double theta);

    void rotateTo(double theta);

    void gimbalSetPose(double yaw_theta, double pitch_theta, double roll_theta);

    void takePhoto();

    void beginVideoCapture();

    void endVideoCapture();

    void startStreaming();

    void stopStreaming();

    void getStreamingFrame();

    void setHome(double lat, double lng);
}
