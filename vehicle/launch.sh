# Start the flight logger first
PYTHONPATH=:./ python3 logger/flight_logger.py &
PID1=$!
# Start the control section of the kernel
PYTHONPATH=:./ python3 kernel/main.py &
PID2=$!
# Start the mission
#PYTHONPATH=$_PYTHONPATH python3 mission/main.py &
#PID3=$!


cleanup() {
    echo "SIGTERM detected. Killing background processes..."
    #kill "$PID3"
    #wait "$PID3"
    kill "$PID2"
    wait "$PID2"
    kill "$PID1" # Make sure to kill our logger after everything else
    wait "$PID1"
    exit 1 # Exit the script after cleanup
}

trap cleanup SIGINT
wait "$PID1" "$PID2" #"$PID3"
