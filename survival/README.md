opencv_stream.py is the main file to run for the drone/simulator that:

 - allows keyboard inputs to control the drone 
 - gets the stream from the drone's camera
 - uses implemented detectors from "detectors" folder to compute on the stream


The detectors folder contains the implemented detectors:

 - contour_detector.py: Uses contours to find a potential trajectory for the drone to follow
 - particle_analysis.py: Uses color segmentation and particle analysis to draw bounding boxes around detected objects
 - particle_analysis_pytorch.py: Uses MiDaS to compute a depth map based on single images


The MiDaS folder contains the steps and a python file to generate a depth map of a video using MiDaS.


The "monocular-vision-based-obstacle-detection" folder contains updated and functioning code based off of this repo:https://github.com/Xaaris/monocular-vision-based-obstacle-detection. The code in their repo doesn't work without many changes. To run this, place the weights file () into the weights folder, create a new virtual enviornment using python 3.7 or earlier, install the dependencies in the "requirements.txt" inside of the folder, and run the "Main.py" file. More detailed instructions are in the Readme inside the folder.


The "requirements.txt" file contains all of the packages required for the project and a bunch of extra random packages that I used at some point during the summer. "pip install -r requirements.txt"


"server.py" and "client.py" are python scripts to open a socket and send a stream of consecutive photos over the network. The client.py is meant to run on a local machine and the server.py file is meant to run on a cloudlet.