# Automated script for creating GRPC python bindings
# TODO: Eventually, we may want to support language/vehicle choice

# Build the datatype files
$PROTOC_PATH -I. \
	--python_out=./python_bindings/ \
       	common.proto \
       	control.proto \
	telemetry.proto \
	result.proto

# Build the service protocols
$PROTOC_PATH -I. \
	--python_out=./python_bindings/ \
	--pyi_out=./python_bindings/ \
	--grpc_python_out=./python_bindings/ \
       	mission_service.proto \
	datastore_service.proto \
	compute_service.proto \
	report_service.proto \
	driver_service.proto
