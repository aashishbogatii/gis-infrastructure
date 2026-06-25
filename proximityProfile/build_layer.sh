# Build the AWS Lambda dependencies layer for the proximity service.
#
# Produces proximity-layer.zip with:
#   python/duckdb, python/yaml, python/fastapi + mangum (+ deps)
#   python/spatial.duckdb_extension
#   python/httpfs.duckdb_extension
#   python/aws.duckdb_extension

set -euo pipefail

DUCKDB_VERSION="${DUCKDB_VERSION:-1.5.4}"
FASTAPI_VERSION="${FASTAPI_VERSION:-0.115.6}"
MANGUM_VERSION="${MANGUM_VERSION:-0.19.0}"
PYVER="${PYVER:-3.14}"
EXT_PLATFORM="linux_amd64"

PLATFORMS="--platform manylinux_2_28_x86_64 --platform manylinux_2_17_x86_64"

PY="${PY:-./riskProfile/.venv/Scripts/python.exe}"

rm -rf layer proximity-layer.zip
mkdir -p layer/python

echo ">> installing Linux wheels (duckdb, PyYAML, fastapi, mangum) for py${PYVER}"
"$PY" -m pip install \
  --target layer/python \
  $PLATFORMS --implementation cp --python-version "$PYVER" \
  --only-binary=:all: \
  "duckdb==${DUCKDB_VERSION}" PyYAML \
  "fastapi==${FASTAPI_VERSION}" "mangum==${MANGUM_VERSION}"

echo ">> downloading DuckDB extensions v${DUCKDB_VERSION}/${EXT_PLATFORM}"
for ext in spatial httpfs aws; do
  curl -fsSL "http://extensions.duckdb.org/v${DUCKDB_VERSION}/${EXT_PLATFORM}/${ext}.duckdb_extension.gz" \
    -o "layer/python/${ext}.duckdb_extension.gz"
  gunzip -f "layer/python/${ext}.duckdb_extension.gz"
done

echo ">> zipping (python/ at the root)"
"$PY" -c "import shutil; shutil.make_archive('proximity-layer','zip','layer')"
echo ">> built proximity-layer.zip ($(du -h proximity-layer.zip | cut -f1))"
echo
echo "publish with:"
echo "  aws lambda publish-layer-version \\"
echo "    --layer-name proximity-deps \\"
echo "    --zip-file fileb://proximity-layer.zip \\"
echo "    --compatible-runtimes python${PYVER} \\"
echo "    --compatible-architectures x86_64"
