# Build the AWS Lambda dependencies layer for the proximity service.
#
# Produces proximity-layer.zip with:
#   python/duckdb, python/yaml
#   python/spatial.duckdb_extension
#   python/httpfs.duckdb_extension

set -euo pipefail

DUCKDB_VERSION="${DUCKDB_VERSION:-1.5.4}"
PYVER="${PYVER:-3.14}"
PLATFORM="manylinux_2_28_x86_64"
EXT_PLATFORM="linux_amd64"

PY="${PY:-./proximity/.venv/Scripts/python.exe}"

rm -rf layer proximity-layer.zip
mkdir -p layer/python

echo ">> installing Linux wheels (duckdb==${DUCKDB_VERSION}, PyYAML) for py${PYVER}/${PLATFORM}"
"$PY" -m pip install \
  --target layer/python \
  --platform "$PLATFORM" --implementation cp --python-version "$PYVER" \
  --only-binary=:all: \
  "duckdb==${DUCKDB_VERSION}" PyYAML

echo ">> downloading DuckDB extensions v${DUCKDB_VERSION}/${EXT_PLATFORM}"
for ext in spatial httpfs aws; do   # aws -> credential_chain provider for the S3 secret
  curl -fsSL "http://extensions.duckdb.org/v${DUCKDB_VERSION}/${EXT_PLATFORM}/${ext}.duckdb_extension.gz" \
    -o "layer/python/${ext}.duckdb_extension.gz"
  gunzip -f "layer/python/${ext}.duckdb_extension.gz"
done

echo ">> zipping (python/ at the root)"
( cd layer && zip -qr ../proximity-layer.zip python )
echo ">> built proximity-layer.zip ($(du -h proximity-layer.zip | cut -f1))"
echo
echo "publish with:"
echo "  aws lambda publish-layer-version \\"
echo "    --layer-name proximity-deps \\"
echo "    --zip-file fileb://proximity-layer.zip \\"
echo "    --compatible-runtimes python${PYVER} \\"
echo "    --compatible-architectures x86_64"
