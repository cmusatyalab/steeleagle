_PYTHONPATH=../protocol/:../protocol/python_bindings/:./
_INTERNALPATH=.internal.yaml
_CONFIGPATH=config.yaml
_PROTOSPATH=../protocol/python_bindings
# Start the flight logger first
PYTHONPATH=$_PYTHONPATH INTERNALPATH=$_INTERNALPATH CONFIGPATH=$_CONFIGPATH python3 logger/flight_logger.py &
PID1=$!
# Start the control section of the kernel
PYTHONPATH=$_PYTHONPATH INTERNALPATH=$_INTERNALPATH CONFIGPATH=$_CONFIGPATH PROTOSPATH=$_PROTOSPATH python3 kernel/control/manager.py &
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
