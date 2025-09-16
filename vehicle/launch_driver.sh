# Start the control section of the core
PYTHONPATH=:./ uv run python drivers/multicopter/devices/Ideal/DigitalPerfect/DigitalPerfect.py &
PID1=$!

cleanup() {
    echo "SIGTERM detected. Killing background processes..."
    kill "$PID1" # Make sure to kill our logger after everything else
    wait "$PID1"
    exit 1 # Exit the script after cleanup
}

trap cleanup SIGINT
wait "$PID1" 
