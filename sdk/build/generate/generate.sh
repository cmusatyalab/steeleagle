PROTOCPATH="python -m grpc_tools.protoc"

cd ../../protocol

# Build the message protocols
$PROTOCPATH -I. \
	--python_out=./bindings \
       	common.proto \
	messages/compute_payload.proto \
	messages/telemetry.proto \
	messages/result.proto \
	testing/testing.proto

# Build the service protocols
$PROTOCPATH -I. \
	--python_out=./bindings \
	--pyi_out=./bindings \
	--grpc_python_out=./bindings/ \
	services/control_service.proto \
       	services/remote_service.proto \
	services/mission_service.proto \
	services/report_service.proto \
	services/flight_log_service.proto \
	services/compute_service.proto \

# Build a global descriptor file
$PROTOCPATH -I. \
	--include_source_info \
	--include_imports \
	--descriptor_set_out=./bindings/protocol.desc \
       	common.proto \
	messages/compute_payload.proto \
	messages/telemetry.proto \
	messages/result.proto \
	testing/testing.proto \
       	services/remote_service.proto \
	services/control_service.proto \
	services/mission_service.proto \
	services/report_service.proto \
	services/flight_log_service.proto \
	services/compute_service.proto \

protol -o bindings --in-place raw ./bindings/protocol.desc

cd ../build/generate

# Construct the API
DESCPATH=../../protocol/bindings/protocol.desc python generate_api.py
