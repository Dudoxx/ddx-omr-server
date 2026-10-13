#!/usr/bin/env bash
# =============================================================================
# ddx-omr-server — fetch the checkbox classifier weights
#
# Downloads omr_model.onnx from hermitkk/omr-checkbox-classifier (AGPL-3.0) at
# a PINNED revision into ./models (gitignored) and verifies its SHA-256.
# A mismatch exits 1 and leaves NO model file in place.
#
# Usage: ./scripts/fetch-weights.sh
# =============================================================================
set -euo pipefail

REPO="hermitkk/omr-checkbox-classifier"
REVISION="046c24e341099033cc565fa5ff0fbaea01fde938"
SHA256="ada735da9eef990edc82e0c98c0621426b8b85bc35f204e3256f7ea89057e115"
FILE="omr_model.onnx"

SERVICE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODELS_DIR="${SERVICE_DIR}/models"
TARGET="${MODELS_DIR}/${FILE}"

command -v uvx >/dev/null 2>&1 || { echo "ERROR: uvx is not on PATH (install uv)" >&2; exit 1; }

mkdir -p "$MODELS_DIR"
STAGE="$(mktemp -d "${MODELS_DIR}/.fetch.XXXXXX")"
trap 'rm -rf "$STAGE"' EXIT INT TERM

echo "fetching ${REPO}@${REVISION} ${FILE}"
uvx --from huggingface_hub hf download "$REPO" "$FILE" \
  --revision "$REVISION" --local-dir "$STAGE" >/dev/null

if [ ! -f "${STAGE}/${FILE}" ]; then
  echo "ERROR: download produced no ${FILE}" >&2
  rm -f "$TARGET"
  exit 1
fi

if command -v sha256sum >/dev/null 2>&1; then
  ACTUAL="$(sha256sum "${STAGE}/${FILE}" | awk '{print $1}')"
else
  ACTUAL="$(shasum -a 256 "${STAGE}/${FILE}" | awk '{print $1}')"
fi
if [ "$ACTUAL" != "$SHA256" ]; then
  echo "ERROR: SHA-256 mismatch for ${FILE}" >&2
  echo "       expected ${SHA256}" >&2
  echo "       got      ${ACTUAL}" >&2
  rm -f "$TARGET"
  exit 1
fi

mv -f "${STAGE}/${FILE}" "$TARGET"
echo "ok ${TARGET}"
echo "sha256 ${ACTUAL}"
