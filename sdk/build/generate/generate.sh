PROTOCPATH="python -m grpc_tools.protoc"

cp -r ../../../protocol ../../temp

cd ../../
_DESCPATH=`pwd`'/protocol/protocol.desc'
cd temp

# Build the message protocols
$PROTOCPATH -I. \
	--python_out=../protocol \
       	common.proto \
	messages/compute_payload.proto \
	messages/telemetry.proto \
	messages/result.proto \
	testing/testing.proto

# Build the service protocols
$PROTOCPATH -I. \
	--python_out=../protocol \
	--pyi_out=../protocol \
	--grpc_python_out=../protocol \
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
	--descriptor_set_out=../protocol/protocol.desc \
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

cd ..
protol -o protocol --in-place raw protocol/protocol.desc
rm -rf temp

cd build/generate

# Construct the API
DESCPATH=$_DESCPATH python generate_api.py
