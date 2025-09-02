_PYTHONPATH=../../:../../../protocol/:../../../protocol/bindings/python/:./
_INTERNALPATH=../../.internal.toml
_CONFIGPATH=../../config.toml
_LAWPATH=../../.laws.toml
_ROOTPATH=../../../
# Start the flight logger first
PYTHONPATH=$_PYTHONPATH INTERNALPATH=$_INTERNALPATH CONFIGPATH=$_CONFIGPATH ROOTPATH=$_ROOTPATH python3 ../../logger/flight_logger.py &
PID1=$!
# Start the test code
PYTHONPATH=$_PYTHONPATH ROOTPATH=$_ROOTPATH python3 -m pytest $1 --log-cli-level=INFO -vv -x &
PID2=$!

cleanup() {
    echo "SIGTERM detected. Killing background processes..."
    kill "$PID2"
    wait "$PID2"
    kill "$PID1" # Make sure to kill our logger after everything else
    wait "$PID1"
    exit 1 # Exit the script after cleanup
}

trap cleanup SIGTERM
wait "$PID2"
kill "$PID1"
wait "$PID1"
exit 1
