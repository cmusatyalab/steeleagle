_PYTHONPATH=../:../../protocol/:../../protocol/python_bindings/:./
_INTERNALPATH=../.internal.toml
_CONFIGPATH=config.toml
_LAWPATH=../.laws.toml
_ROOTPATH=../../
# Start the flight logger first
PYTHONPATH=$_PYTHONPATH INTERNALPATH=$_INTERNALPATH CONFIGPATH=$_CONFIGPATH python3 ../logger/flight_logger.py &
PID1=$!
# Start the test code
PYTHONPATH=$_PYTHONPATH CONFIGPATH=$_CONFIGPATH INTERNALPATH=$_INTERNALPATH LAWPATH=$_LAWPATH ROOTPATH=$_ROOTPATH python3 -m pytest grpc_test.py --log-cli-level=INFO -vv

cleanup() {
    echo "SIGTERM detected. Killing background processes..."
    kill "$PID1" # Make sure to kill our logger after everything else
    wait "$PID1"
    exit 1 # Exit the script after cleanup
}

trap cleanup SIGINT
wait "$PID1"
