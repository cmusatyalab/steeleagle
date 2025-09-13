_INTERNALPATH=../../.internal.toml
_CONFIGPATH=../../config.toml
# Start the flight logger first
PYTHONPATH=:../../ INTERNALPATH=$_INTERNALPATH CONFIGPATH=$_CONFIGPATH python3 ../../logger/flight_logger.py &
PID1=$!
# Start the test code
PYTHONPATH=:../../ python3 -m pytest $@ --log-cli-level=INFO -vv -x &
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
