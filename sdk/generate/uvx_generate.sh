#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SDK_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"     # .../steeleagle/sdk

PROTO_ROOT="$SDK_ROOT/src"                  # must contain steeleagle_sdk/protocol/...
OUTROOT="$SDK_ROOT/build/src"
DESC_OUT="$OUTROOT/steeleagle_sdk/protocol/protocol.desc"

if ! command -v uvx >/dev/null 2>&1; then
  echo "ERROR: uvx not found in PATH" >&2
  exit 1
fi

if [[ $# -ne 0 && $# -ne 2 ]]; then
  echo "ERROR: provide none or two args (python version & grpcio-tools version)" >&2
  exit 1
fi

PROTOCPATH="uvx --from grpcio-tools python-grpc-tools-protoc"
if [[ $# -eq 2 ]]; then
  PROTOCPATH="uvx --python $1 --from grpcio-tools==$2 python-grpc-tools-protoc"
fi

# Canonical proto paths (relative to -I "$PROTO_ROOT")
MSG_PROTOS=(
  "steeleagle_sdk/protocol/common.proto"
  "steeleagle_sdk/protocol/messages/telemetry.proto"
  "steeleagle_sdk/protocol/messages/result.proto"
  "steeleagle_sdk/protocol/testing/testing.proto"
)

SVC_PROTOS=(
  "steeleagle_sdk/protocol/services/control_service.proto"
  "steeleagle_sdk/protocol/services/remote_service.proto"
  "steeleagle_sdk/protocol/services/mission_service.proto"
  "steeleagle_sdk/protocol/services/report_service.proto"
  "steeleagle_sdk/protocol/services/flight_log_service.proto"
  "steeleagle_sdk/protocol/services/compute_service.proto"
)

ALL_PROTOS=("${MSG_PROTOS[@]}" "${SVC_PROTOS[@]}")

mkdir -p "$(dirname "$DESC_OUT")"
mkdir -p "$OUTROOT"

echo "Proto root:   $PROTO_ROOT"
echo "Out root:     $OUTROOT"
echo "Desc out:     $DESC_OUT"

# --- HARD CHECK: make sure protoc can see the files exactly as referenced ---
for f in "${ALL_PROTOS[@]}"; do
  if [[ ! -f "$PROTO_ROOT/$f" ]]; then
    echo "ERROR: missing proto: $PROTO_ROOT/$f" >&2
    exit 1
  fi
done

# --- Build message protos ---
$PROTOCPATH -I "$PROTO_ROOT" \
  -I "$PROTO_ROOT/steeleagle_sdk/protocol" \
  --python_out="$OUTROOT" \
  "${MSG_PROTOS[@]}"

# --- Build service protos ---
$PROTOCPATH -I "$PROTO_ROOT" \
  -I "$PROTO_ROOT/steeleagle_sdk/protocol" \  
  --python_out="$OUTROOT" \
  --pyi_out="$OUTROOT" \
  --grpc_python_out="$OUTROOT" \
  "${SVC_PROTOS[@]}"

# --- Build descriptor set ---
$PROTOCPATH -I "$PROTO_ROOT" \
  -I "$PROTO_ROOT/steeleagle_sdk/protocol" \
  --include_source_info \
  --include_imports \
  --descriptor_set_out="$DESC_OUT" \
  "${ALL_PROTOS[@]}"

echo "Protobuf generation complete."
