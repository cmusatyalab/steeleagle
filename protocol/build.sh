# Automated script for creating GRPC python bindings
# TODO: Eventually, we may want to support language/vehicle choice

# Build the datatype files
python3 -m grpc_tools.protoc -I. \
	--python_out=./python_bindings/ \
       	common.proto \
	telemetry.proto \
	result.proto

# Build the service protocols
python3 -m grpc_tools.protoc -I. \
	--python_out=./python_bindings/ \
	--pyi_out=./python_bindings/ \
	--grpc_python_out=./python_bindings/ \
       	mission_service.proto \
	datastore_service.proto \
	compute_service.proto \
	report_service.proto \
	multicopter_service.proto
