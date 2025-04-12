
if [ -z "$PROTOC_PATH" ]; then
  echo "Error: protoc path not specified."
  exit 1
fi

$PROTOC_PATH --python_out=. *.proto
