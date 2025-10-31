PROTOCPATH="python -m grpc_tools.protoc"

# Build the message protocols
$PROTOCPATH -I. \
	--python_out=../drivers/proto_build \
       	common.proto \
	messages/telemetry.proto \
	messages/result.proto

# Build the service protocols
$PROTOCPATH -I. \
	--python_out=../drivers/proto_build \
	--grpc_python_out=../drivers/proto_build \
	services/control_service.proto


cp ../sdk/protocol/rpc_helpers.py ../drivers/proto_build/rpc_helpers.py