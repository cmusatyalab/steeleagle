# Automated script for creating GRPC python bindings
# TODO: Eventually, we may want to support language/vehicle choice

# Build the datatype files
$PROTOCPATH -I. \
	--python_out=./python_bindings/ \
       	common.proto \
       	swarm_control.proto \
	telemetry.proto \
	result.proto \
	testing.proto

# Build the service protocols
$PROTOCPATH -I. \
	--python_out=./python_bindings/ \
	--pyi_out=./python_bindings/ \
	--grpc_python_out=./python_bindings/ \
       	mission_service.proto \
	datastore_service.proto \
	compute_service.proto \
	report_service.proto \
	control_service.proto \
	flight_log_service.proto
