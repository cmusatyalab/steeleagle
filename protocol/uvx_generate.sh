#!/usr/bin/env bash
set -euo pipefail

# --- locate repo paths ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

PROTO_ROOT="$REPO_ROOT/protocol"   # input .proto files live here
SDK_DIR="$REPO_ROOT/sdk"
OUTPATH="$SDK_DIR/src/steeleagle_sdk/protocol"  # output python files live here
DESC_OUT="$OUTPATH/protocol.desc"  # descriptor output

# --- sanity checks ---
if ! command -v "uvx" >/dev/null 2>&1; then
  echo "ERROR: uvx not found in PATH" >&2
  exit 1
fi

if [[ $# > 2 || $# = 1 ]]; then
  echo "ERROR: incorrect number of arguments, either provide none or two (python version & grpc version)"
  exit 1
fi

PROTOCPATH="uvx --from grpcio-tools python-grpc-tools-protoc"
if [[ $# = 2 ]]; then
  PROTOCPATH="uvx --python $1 --from grpcio-tools==$2 python-grpc-tools-protoc"
fi

mkdir -p "$(dirname "$DESC_OUT")"
mkdir -p "$OUTPATH"

# --- proto file lists ---
MSG_PROTOS=(
  "$PROTO_ROOT/common.proto"
  "$PROTO_ROOT/messages/telemetry.proto"
  "$PROTO_ROOT/messages/result.proto"
  "$PROTO_ROOT/testing/testing.proto"
)

SVC_PROTOS=(
  "$PROTO_ROOT/services/control_service.proto"
  "$PROTO_ROOT/services/remote_service.proto"
  "$PROTO_ROOT/services/mission_service.proto"
  "$PROTO_ROOT/services/report_service.proto"
  "$PROTO_ROOT/services/flight_log_service.proto"
  "$PROTO_ROOT/services/compute_service.proto"
)

ALL_PROTOS=(
  "${MSG_PROTOS[@]}"
  "${SVC_PROTOS[@]}"
)

if [[ $# = 2 ]]; then
  echo "Using python: $1"
  echo "Using grpcio: $2"
fi
echo "Proto root:   $PROTO_ROOT"
echo "Out path:     $OUTPATH"
echo "Desc out:     $DESC_OUT"

# --- Build the message protocols (Python *_pb2.py) ---
$PROTOCPATH -I "$PROTO_ROOT" \
  --python_out="$OUTPATH" \
  "${MSG_PROTOS[@]}"

# --- Build the service protocols (Python + gRPC stubs + .pyi) ---
$PROTOCPATH -I "$PROTO_ROOT" \
  --python_out="$OUTPATH" \
  --grpc_python_out="$OUTPATH" \
  "${SVC_PROTOS[@]}"

# --- Build a global descriptor file ---
$PROTOCPATH -I "$PROTO_ROOT" \
  --include_source_info \
  --include_imports \
  --descriptor_set_out="$DESC_OUT" \
  "${ALL_PROTOS[@]}"

echo "Protobuf generation complete."
