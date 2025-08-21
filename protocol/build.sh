# Automated script for creating GRPC python bindings
# TODO: Eventually, we may want to support language/vehicle choice

# Build the service protocols
$PROTOCPATH -I. \
	--python_out=./bindings/python/ \
       	common.proto \
       	services/remote_control_service.proto \
	messages/compute_payload.proto \
	messages/telemetry.proto \
	messages/result.proto \
	testing/testing.proto

# Build the service protocols
$PROTOCPATH -I. \
	--python_out=./bindings/python/ \
	--pyi_out=./bindings/python/ \
	--grpc_python_out=./bindings/python/ \
	--descriptor_set_out=./services.desc \
	--include_imports \
	services/control_service.proto \
	services/mission_service.proto \
	services/report_service.proto \
	services/flight_log_service.proto \
	services/compute_service.proto \
