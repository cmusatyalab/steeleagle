# Camera Calibration

### How to calibrate a new camera

In order to use this project with a camera model for which no calibration data has been added yet, print the attached checkerboard, take pictures of it from various angles and put them in the calibration_images folder.
Then use the CameraCalibration.py script to generate the camera matrix and rotation/translation matrix.
Link the just created camera model in main.py and your pictures will be calibrated with the appropriate matrices.