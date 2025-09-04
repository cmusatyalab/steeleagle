# Automated script for creating GRPC python bindings
# TODO: Eventually, we may want to support language/vehicle choice

# Build the message protocols
$PROTOCPATH -I. \
	--python_out=./bindings/python/ \
       	common.proto \
	messages/compute_payload.proto \
	messages/telemetry.proto \
	messages/result.proto \
	testing/testing.proto

# Build the service protocols
$PROTOCPATH -I. \
	--python_out=./bindings/python/ \
	--pyi_out=./bindings/python/ \
	--grpc_python_out=./bindings/python/ \
	services/control_service.proto \
       	services/remote_service.proto \
	services/mission_service.proto \
	services/report_service.proto \
	services/flight_log_service.proto \
	services/compute_service.proto \

# Build a global descriptor file
$PROTOCPATH -I. \
	--descriptor_set_out=./protocol.desc \
	--include_imports \
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
