PROTOCPATH="python3 -m grpc_tools.protoc"

cd ../../protocol

# Build the message protocols
$PROTOCPATH -I. \
	--python_out=../build/src/steeleagle_sdk/protocol \
       	common.proto \
	messages/compute_payload.proto \
	messages/telemetry.proto \
	messages/result.proto \
	testing/testing.proto

# Build the service protocols
$PROTOCPATH -I. \
	--python_out=../build/src/steeleagle_sdk/protocol/ \
	--pyi_out=../build/src/steeleagle_sdk/protocol/ \
	--grpc_python_out=../build/src/steeleagle_sdk/protocol/ \
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
	--descriptor_set_out=../build/src/steeleagle_sdk/protocol/protocol.desc \
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

cd ../build/generate

protol -o ../src/steeleagle_sdk/protocol --in-place raw ../src/steeleagle_sdk/protocol/protocol.desc

# Construct the API
DESCPATH=../src/steeleagle_sdk/protocol/protocol.desc python3 generate_api.py
