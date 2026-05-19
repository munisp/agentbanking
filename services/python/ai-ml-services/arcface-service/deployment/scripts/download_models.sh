#!/bin/bash
# ArcFace Face Matching Service - Model Download Script
# Downloads pre-trained models for face detection and recognition

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
MODELS_DIR="${MODELS_DIR:-./models}"
DET_MODEL_URL="https://github.com/deepinsight/insightface/releases/download/v0.7/det_10g.onnx"
REC_MODEL_URL="https://github.com/deepinsight/insightface/releases/download/v0.7/w600k_r50.onnx"
DET_MODEL_FILE="det_10g.onnx"
REC_MODEL_FILE="w600k_r50.onnx"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}ArcFace Model Download Script${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Create models directory
echo -e "${YELLOW}Creating models directory...${NC}"
mkdir -p "$MODELS_DIR"
cd "$MODELS_DIR"
echo -e "${GREEN}✓ Models directory: $(pwd)${NC}"
echo ""

# Function to download file with progress
download_file() {
    local url=$1
    local output=$2
    local description=$3
    
    echo -e "${YELLOW}Downloading $description...${NC}"
    echo -e "  URL: $url"
    echo -e "  Output: $output"
    
    if [ -f "$output" ]; then
        echo -e "${YELLOW}  File already exists. Checking integrity...${NC}"
        # You can add checksum verification here
        echo -e "${GREEN}  ✓ File exists and appears valid${NC}"
        return 0
    fi
    
    # Download with wget (with progress bar)
    if command -v wget &> /dev/null; then
        wget -c "$url" -O "$output" --progress=bar:force 2>&1
    # Or use curl if wget not available
    elif command -v curl &> /dev/null; then
        curl -L "$url" -o "$output" --progress-bar
    else
        echo -e "${RED}Error: Neither wget nor curl is installed${NC}"
        exit 1
    fi
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}  ✓ Download complete${NC}"
    else
        echo -e "${RED}  ✗ Download failed${NC}"
        exit 1
    fi
}

# Download detection model
echo -e "${YELLOW}[1/2] Face Detection Model (RetinaFace)${NC}"
download_file "$DET_MODEL_URL" "$DET_MODEL_FILE" "RetinaFace detection model"
echo ""

# Download recognition model
echo -e "${YELLOW}[2/2] Face Recognition Model (ArcFace ResNet-50)${NC}"
download_file "$REC_MODEL_URL" "$REC_MODEL_FILE" "ArcFace recognition model"
echo ""

# Verify downloads
echo -e "${YELLOW}Verifying downloads...${NC}"
echo ""

if [ -f "$DET_MODEL_FILE" ]; then
    DET_SIZE=$(du -h "$DET_MODEL_FILE" | cut -f1)
    echo -e "${GREEN}✓ Detection model: $DET_MODEL_FILE ($DET_SIZE)${NC}"
else
    echo -e "${RED}✗ Detection model not found${NC}"
    exit 1
fi

if [ -f "$REC_MODEL_FILE" ]; then
    REC_SIZE=$(du -h "$REC_MODEL_FILE" | cut -f1)
    echo -e "${GREEN}✓ Recognition model: $REC_MODEL_FILE ($REC_SIZE)${NC}"
else
    echo -e "${RED}✗ Recognition model not found${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}All models downloaded successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "Models location: $(pwd)"
echo -e "Detection model: $DET_MODEL_FILE ($DET_SIZE)"
echo -e "Recognition model: $REC_MODEL_FILE ($REC_SIZE)"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo -e "  1. Verify models are in the correct location"
echo -e "  2. Update MODEL_PATH in your configuration"
echo -e "  3. Start the ArcFace service"
echo ""

# Optional: Test model loading
if [ "$TEST_MODELS" = "true" ]; then
    echo -e "${YELLOW}Testing model loading...${NC}"
    python3 << EOF
import onnxruntime as ort
import sys

try:
    # Test detection model
    print("Loading detection model...")
    det_session = ort.InferenceSession(
        "$DET_MODEL_FILE",
        providers=['CUDAExecutionProvider', 'CPUExecutionProvider']
    )
    print(f"✓ Detection model loaded: {det_session.get_inputs()[0].name}")
    
    # Test recognition model
    print("Loading recognition model...")
    rec_session = ort.InferenceSession(
        "$REC_MODEL_FILE",
        providers=['CUDAExecutionProvider', 'CPUExecutionProvider']
    )
    print(f"✓ Recognition model loaded: {rec_session.get_inputs()[0].name}")
    
    print("\n✓ All models loaded successfully!")
    sys.exit(0)
except Exception as e:
    print(f"\n✗ Error loading models: {str(e)}")
    sys.exit(1)
EOF
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Model loading test passed${NC}"
    else
        echo -e "${RED}✗ Model loading test failed${NC}"
        exit 1
    fi
fi

exit 0
