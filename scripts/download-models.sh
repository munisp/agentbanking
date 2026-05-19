#!/usr/bin/env bash
# download-models.sh — Fetch ML model weights for biometric services
#
# Usage: bash scripts/download-models.sh
#
# Downloads:
#   - InsightFace buffalo_l pack (ArcFace w600k_r50, RetinaFace det_10g, genderage, 2d106det, 1k3d68)
#   - MiniFASNet anti-spoofing models (V2, V1SE)
#
# Total download: ~380 MB

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Downloading biometric model weights ==="

# ── ArcFace / InsightFace buffalo_l ──────────────────────────────────────────
ARCFACE_DIR="$PROJECT_DIR/services/python/ai-ml-services/arcface-service/models"
FACE_MATCH_DIR="$PROJECT_DIR/services/python/face-matching/models"

mkdir -p "$ARCFACE_DIR" "$FACE_MATCH_DIR"

if [ ! -f "$ARCFACE_DIR/w600k_r50.onnx" ]; then
  echo "[1/3] Downloading InsightFace buffalo_l model pack..."
  TMPDIR=$(mktemp -d)
  wget -q -O "$TMPDIR/buffalo_l.zip" \
    "https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip"
  unzip -o -q "$TMPDIR/buffalo_l.zip" -d "$ARCFACE_DIR/"
  # If unzipped into a subdirectory, flatten
  if [ -d "$ARCFACE_DIR/buffalo_l" ]; then
    mv "$ARCFACE_DIR/buffalo_l/"*.onnx "$ARCFACE_DIR/" 2>/dev/null || true
    rmdir "$ARCFACE_DIR/buffalo_l" 2>/dev/null || true
  fi
  rm -rf "$TMPDIR"
  echo "  ✓ ArcFace models downloaded to $ARCFACE_DIR"
else
  echo "  ✓ ArcFace models already present"
fi

# Copy to face-matching service
for f in det_10g.onnx w600k_r50.onnx genderage.onnx; do
  if [ -f "$ARCFACE_DIR/$f" ] && [ ! -f "$FACE_MATCH_DIR/$f" ]; then
    cp "$ARCFACE_DIR/$f" "$FACE_MATCH_DIR/$f"
  fi
done
echo "  ✓ Face matching models synced"

# ── MiniFASNet Anti-Spoofing ─────────────────────────────────────────────────
LIVENESS_DIR="$PROJECT_DIR/services/python/liveness-detection/models"
BIOMETRIC_DIR="$PROJECT_DIR/services/python/biometric/face-verification/models"

mkdir -p "$LIVENESS_DIR" "$BIOMETRIC_DIR"

if [ ! -f "$LIVENESS_DIR/MiniFASNetV2.pth" ]; then
  echo "[2/3] Downloading MiniFASNet anti-spoofing models..."
  wget -q -O "$LIVENESS_DIR/MiniFASNetV2.pth" \
    "https://github.com/minivision-ai/Silent-Face-Anti-Spoofing/raw/master/resources/anti_spoof_models/2.7_80x80_MiniFASNetV2.pth"
  wget -q -O "$LIVENESS_DIR/MiniFASNetV1SE.pth" \
    "https://github.com/minivision-ai/Silent-Face-Anti-Spoofing/raw/master/resources/anti_spoof_models/4_0_0_80x80_MiniFASNetV1SE.pth"
  echo "  ✓ MiniFASNet models downloaded to $LIVENESS_DIR"
else
  echo "  ✓ MiniFASNet models already present"
fi

# Copy to biometric service
for f in MiniFASNetV2.pth MiniFASNetV1SE.pth; do
  if [ -f "$LIVENESS_DIR/$f" ] && [ ! -f "$BIOMETRIC_DIR/$f" ]; then
    cp "$LIVENESS_DIR/$f" "$BIOMETRIC_DIR/$f"
  fi
done
echo "  ✓ Biometric service models synced"

# ── Deepfake Detection (EfficientNet) ────────────────────────────────────────
DEEPFAKE_DIR="$PROJECT_DIR/services/python/deepfake-detection/models"
mkdir -p "$DEEPFAKE_DIR"

echo "[3/3] Deepfake model: EfficientNet-B0 weights are downloaded automatically by PyTorch on first run"
echo "  ✓ No manual download needed for deepfake service"

# ── Summary ──────────────────────────────────────────────────────────────────
echo ""
echo "=== Model download complete ==="
echo "ArcFace:     $(ls -1 "$ARCFACE_DIR"/*.onnx 2>/dev/null | wc -l) ONNX files"
echo "MiniFASNet:  $(ls -1 "$LIVENESS_DIR"/*.pth 2>/dev/null | wc -l) PTH files"
echo "Face Match:  $(ls -1 "$FACE_MATCH_DIR"/*.onnx 2>/dev/null | wc -l) ONNX files"
echo "Biometric:   $(ls -1 "$BIOMETRIC_DIR"/*.pth 2>/dev/null | wc -l) PTH files"
echo ""
echo "Total size: $(du -sh "$PROJECT_DIR/services/python/*/models" "$PROJECT_DIR/services/python/*/*/models" 2>/dev/null | tail -1 | awk '{print $1}')"
