_PYTHONPATH=../protocol/:../protocol/bindings/python/:./
# Start the flight logger first
PYTHONPATH=$_PYTHONPATH python3 logger/flight_logger.py &
PID1=$!
# Start the control section of the core
PYTHONPATH=$_PYTHONPATH python3 core/main.py &
PID2=$!

cleanup() {
    echo "SIGTERM detected. Killing background processes..."
    kill "$PID2"
    wait "$PID2"
    kill "$PID1" # Make sure to kill our logger after everything else
    wait "$PID1"
    exit 1 # Exit the script after cleanup
}

trap cleanup SIGINT
wait "$PID1" "$PID2"
