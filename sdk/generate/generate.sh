PROTOCPATH="python -m grpc_tools.protoc"

cd ../src

_DESCPATH=`pwd`'/steeleagle_sdk/protocol/protocol.desc'

# Build the message protocols
$PROTOCPATH -I. \
	--python_out=. \
       	steeleagle_sdk/protocol/common.proto \
	steeleagle_sdk/protocol/messages/telemetry.proto \
	steeleagle_sdk/protocol/messages/result.proto \
	steeleagle_sdk/protocol/testing/testing.proto \

# Build the service protocols
$PROTOCPATH -I. \
	--python_out=. \
	--pyi_out=.  \
	--grpc_python_out=. \
	steeleagle_sdk/protocol/services/control_service.proto \
       	steeleagle_sdk/protocol/services/remote_service.proto \
	steeleagle_sdk/protocol/services/mission_service.proto \
	steeleagle_sdk/protocol/services/report_service.proto \
	steeleagle_sdk/protocol/services/flight_log_service.proto \
	steeleagle_sdk/protocol/services/compute_service.proto \

# Build a global descriptor file
$PROTOCPATH -I. \
	--include_source_info \
	--include_imports \
	--descriptor_set_out=steeleagle_sdk/protocol/protocol.desc \
       	steeleagle_sdk/protocol/common.proto \
	steeleagle_sdk/protocol/messages/telemetry.proto \
	steeleagle_sdk/protocol/messages/result.proto \
	steeleagle_sdk/protocol/testing/testing.proto \
       	steeleagle_sdk/protocol/services/remote_service.proto \
	steeleagle_sdk/protocol/services/control_service.proto \
	steeleagle_sdk/protocol/services/mission_service.proto \
	steeleagle_sdk/protocol/services/report_service.proto \
	steeleagle_sdk/protocol/services/flight_log_service.proto \
	steeleagle_sdk/protocol/services/compute_service.proto \

# Construct the API
#DESCPATH=$_DESCPATH python ../generate/generate_api.py
