#!/usr/bin/env bash
set -e

DRIVER_NAME="$1"
if [ -z "$DRIVER_NAME" ]; then
    echo "Usage: $0 <driver_name>"
    exit 1
fi

PROTOCPATH="python -m grpc_tools.protoc"
OUT_DIR="../drivers/${DRIVER_NAME}/proto_build"

mkdir -p "$OUT_DIR"

# Build message protocols
$PROTOCPATH -I. \
    --python_out="$OUT_DIR" \
    common.proto \
    messages/telemetry.proto \
    messages/result.proto

# Build service protocols
$PROTOCPATH -I. \
    --python_out="$OUT_DIR" \
    --grpc_python_out="$OUT_DIR" \
    services/control_service.proto
