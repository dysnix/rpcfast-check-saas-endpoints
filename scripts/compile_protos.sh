#!/bin/bash
set -e

PROTO_DIR=${PROTO_DIR:-/app/proto}
OUT_DIR=${OUT_DIR:-/app/app/proto_compiled}

mkdir -p "$OUT_DIR"
touch "$OUT_DIR/__init__.py"

python -m grpc_tools.protoc \
  -I"$PROTO_DIR" \
  --python_out="$OUT_DIR" \
  --grpc_python_out="$OUT_DIR" \
  "$PROTO_DIR/solana-storage.proto" \
  "$PROTO_DIR/geyser.proto" \
  "$PROTO_DIR/shared.proto" \
  "$PROTO_DIR/shredstream.proto"

# Fix imports in generated files to use relative imports within the package
cd "$OUT_DIR"
sed -i.bak 's/^import solana_storage_pb2/from . import solana_storage_pb2/' geyser_pb2.py
sed -i.bak 's/^from solana_storage_pb2/from .solana_storage_pb2/' geyser_pb2.py
sed -i.bak 's/^import geyser_pb2/from . import geyser_pb2/' geyser_pb2_grpc.py
sed -i.bak 's/^import shared_pb2/from . import shared_pb2/' shredstream_pb2.py
sed -i.bak 's/^import shredstream_pb2/from . import shredstream_pb2/' shredstream_pb2_grpc.py
rm -f *.bak

echo "Proto compilation complete: $OUT_DIR"
