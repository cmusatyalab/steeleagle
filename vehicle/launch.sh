# Start the flight logger first
PYTHONPATH=:./ python3 logger/flight_logger.py &
PID1=$!
# Start the control section of the kernel
PYTHONPATH=:./ uv run python kernel/main.py &
PID2=$!
# Start the mission
PYTHONPATH=:./ uv run python mission/main.py &
PID3=$!
# Start the control section of the core
PYTHONPATH=:./ uv run python drivers/multicopter/devices/Ideal/DigitalPerfect/DigitalPerfect.py &
PID4=$!



cleanup() {
    echo "SIGTERM detected. Killing background processes..."
	kill "$PID4"
    wait "$PID4"
    kill "$PID3"
    wait "$PID3"
    kill "$PID2"
    wait "$PID2"
    kill "$PID1" # Make sure to kill our logger after everything else
    wait "$PID1"
    exit 1 # Exit the script after cleanup
}

trap cleanup SIGINT
wait "$PID2" "$PID3" "$PID4" "$PID1"
