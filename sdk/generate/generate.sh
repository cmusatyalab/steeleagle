#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../" && pwd)"

PROTO_ROOT="$REPO_ROOT/protocol"
SDK_DIR="$REPO_ROOT/sdk"
PKG_ROOT="$SDK_DIR/src/steeleagle_sdk/protocol"
DESC_OUT="$PKG_ROOT/protocol.desc"

MSG_PROTOS=(
  "common.proto"
  "messages/telemetry.proto"
  "messages/result.proto"
  "testing/testing.proto"
)

SVC_PROTOS=(
  "services/control_service.proto"
  "services/remote_service.proto"
  "services/mission_service.proto"
  "services/report_service.proto"
  "services/flight_log_service.proto"
  "services/compute_service.proto"
)

ALL_PROTOS=("${MSG_PROTOS[@]}" "${SVC_PROTOS[@]}")

die() { echo "ERROR: $*" >&2; exit 1; }

command -v uv >/dev/null 2>&1 || die "uv not found"
[[ -d "$PROTO_ROOT" ]] || die "missing: $PROTO_ROOT"
[[ -d "$SDK_DIR" ]] || die "missing: $SDK_DIR"
mkdir -p "$PKG_ROOT"

echo "Proto root: $PROTO_ROOT"
echo "Out pkg:    $PKG_ROOT"
echo "Desc out:   $DESC_OUT"
echo "SDK dir:    $SDK_DIR"

pushd "$SDK_DIR" >/dev/null

uv run python -c "import grpc_tools.protoc" >/dev/null 2>&1 \
  || die "grpcio-tools missing in uv env. Run: cd \"$SDK_DIR\" && uv sync --extra dev"

uv run python -c "import protoletariat" >/dev/null 2>&1 \
  || die "protoletariat missing in uv env. Add it to dev deps and run: cd \"$SDK_DIR\" && uv sync --extra dev"

PROTOC=(uv run python -m grpc_tools.protoc)

# Compile (keep cwd at SDK_DIR so uv uses sdk/.venv)
"${PROTOC[@]}" -I "$PROTO_ROOT" \
  --python_out="$PKG_ROOT" \
  "${MSG_PROTOS[@]/#/$PROTO_ROOT/}"

"${PROTOC[@]}" -I "$PROTO_ROOT" \
  --python_out="$PKG_ROOT" \
  --grpc_python_out="$PKG_ROOT" \
  --pyi_out="$PKG_ROOT" \
  "${SVC_PROTOS[@]/#/$PROTO_ROOT/}"

"${PROTOC[@]}" -I "$PROTO_ROOT" \
  --include_source_info \
  --include_imports \
  --descriptor_set_out="$DESC_OUT" \
  "${ALL_PROTOS[@]/#/$PROTO_ROOT/}"

uv run protol \
  --in-place \
  -o "$SDK_DIR/src" \
  "$PKG_ROOT"


popd >/dev/null

echo "Done."
