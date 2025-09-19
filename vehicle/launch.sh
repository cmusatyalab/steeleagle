# Start the control section of the kernel
PYTHONPATH=:./ uv run python kernel/main.py &
PID1=$!
sleep 0.1
# Start the control section of the core
PYTHONPATH=:./ uv run python drivers/multicopter/devices/Ideal/DigitalPerfect/DigitalPerfect.py &
PID2=$!
# Start the mission
PYTHONPATH=:./ uv run python mission/main.py &
PID3=$!



cleanup() {
    kill "$PID3"
    wait "$PID3"
    kill "$PID2"
    wait "$PID2"
    kill "$PID1"
    wait "$PID1"
    exit 1 # Exit the script after cleanup
}

trap cleanup SIGINT
wait "$PID1"
