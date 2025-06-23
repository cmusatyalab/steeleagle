#!/bin/sh

set -e

cd `dirname $0`

if [ -z "$(which uvx)" ]; then
  echo "Error: uvx not found."
  exit 1
fi

# Use uvx to download and run the protoc compiler.
#
# - there is a builtin --pyi_out in protoc, but the generated stubs still
#   return some errors, the mypy-protobuf generated stubs seem to be better
# - the docker build was using protoc 29.4
# - grpcio-tools 1.73.0 uses protoc 31
# - grpcio-tools 1.72.1 uses protoc 30
# - grpcio-tools 1.71.0 uses protoc 29
# - grpcio-tools <1.73.0 doesn't declare an entry point so we use python -m
#
#PROTOC_PATH="uvx --from grpcio-tools==1.73.0 --with mypy-protobuf==3.6.0 python-grpc-tools-protoc"
PROTOC_PATH="uvx --from grpcio-tools==1.71.0 --with mypy-protobuf==3.6.0 python -m grpc_tools.protoc"

$PROTOC_PATH --proto_path=. --python_out=. --mypy_out=. *.proto

# use sed to fix up imports from absolute to relative
sed -i -e 's/import common_pb2 as/from . import common_pb2 as/' \
       -e 's/from common_pb2 import/from .common_pb2 import/' \
       -e 's/import controlplane_pb2 as/from . import controlplane_pb2 as/' \
       -e 's/from controlplane_pb2 import/from .controlplane_pb2 import/' \
       -e 's/import dataplane_pb2 as/from . import dataplane_pb2 as/' \
       -e 's/from dataplane_pb2 import/from .dataplane_pb2 import/' \
    ./*_pb2.py ./*_pb2.pyi
