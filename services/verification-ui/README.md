# 54agent Identity Verification UI

A React-based identity verification interface using liveness detection for KYC/KYB verification.

## Features

- **Liveness Detection**: Real-time face liveness check with challenge-response
- **Document Capture**: Front and back ID card/document capture
- **Selfie Capture**: Secure selfie capture with liveness proof
- **Proof Generation**: Cryptographically secure verification proofs
- **Mobile Responsive**: Optimized for mobile and desktop browsers

## Technology Stack

- React 19
- TypeScript
- Tailwind CSS 4
- Vite 7
- Custom liveness detection engine

## Setup

### Prerequisites

- Node.js 18+
- npm or yarn

### Installation

```bash
cd services/verification-ui
npm install
```

### Configuration

Create a `.env` file based on `.env.example`:

```bash
cp .env.example .env
```

Configure the verification service URL and API key:

```env
VITE_VERIFICATION_API_URL=http://localhost:8080
VITE_KYC_FLOW_API_KEY=your_kyc_flow_api_key_here
```

**Important**: The `VITE_KYC_FLOW_API_KEY` must match the `KYC_FLOW_API_KEY` set in the verification-service `.env` file.

### Development

```bash
npm run dev
```

The app will be available at http://localhost:8005

### Build

```bash
npm run build
```

The production build will be in the `dist/` directory.

### Docker

Build the Docker image:

```bash
docker build -t 54agent-verification-ui --build-arg VITE_VERIFICATION_API_URL=https://api.54agent.com .
```

Run the container:

```bash
docker run -p 8005:80 54agent-verification-ui
```

## Usage

### URL Parameters

The verification UI accepts the following URL parameters:

- `verification_id` (required): The verification session ID from the verification service
- `redirect_url` (optional): URL to redirect after successful verification
- `metadata` (optional): JSON-encoded metadata to pass to verification service

Example:
```
http://localhost:8005?verification_id=ver_123&redirect_url=https://app.example.com/success&metadata={"user_id":"123"}
```

### Verification Flow

1. **Welcome Screen**: User sees instructions and starts verification
2. **Document Capture**: 
   - Capture front of ID card
   - Capture back of ID card
3. **Liveness Check**:
   - Camera initialization
   - 4 random challenges (turn left, turn right, smile, look up/down)
   - Real-time motion and light detection
4. **Verification**:
   - Liveness proof validation
   - Document verification
   - Face matching
5. **Result**: Success or failure with confidence scores

## Integration

### With Verification Service

The UI sends verification data to the verification service at `/kyc/verify`:

```typescript
{
  "endUserInfo": {
    "id": "verification_id"
  },
  "document": {
    "type": "id_card",
    "country": "NG",
    "frontImage": "base64_image",
    "backImage": "base64_image"
  },
  "selfie": {
    "image": "base64_image"
  },
  "livenessProof": {
    "sessionId": "session_id",
    "timestamp": 1234567890,
    "confidence": 0.95,
    "verdict": "VERIFIED",
    "signals": {
      "motion": 0.8,
      "challengePassed": true,
      "timingVariance": 0.3,
      "lightVariance": 0.5,
      "frameDiff": 0.4
    },
    "hash": "proof_hash"
  }
}
```

### Liveness Detection

The liveness detection engine includes:

- **Motion Detection**: Analyzes frame-to-frame motion
- **Challenge System**: Random challenges to prove liveness
- **Timing Analysis**: Validates natural human response times
- **Light Variance**: Detects screen replay attacks
- **Frame Difference**: Identifies static images

## Security

- All proofs include cryptographic hashes
- Liveness signals validated server-side
- Proof expiration (5 minutes)
- Minimum confidence thresholds
- Challenge randomization
- Replay attack prevention

## Browser Support

- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)
- Mobile browsers (iOS Safari, Chrome)

Camera access required - HTTPS recommended for production.

## Development Notes

### File Structure

```
src/
├── liveness/           # Liveness detection engine
│   ├── camera.ts       # Camera initialization
│   ├── challengeEngine.ts  # Challenge generation
│   ├── frameEngine.ts   # Frame capture and buffering
│   ├── motionEngine.ts  # Motion detection
│   ├── lightEngine.ts   # Light analysis
│   ├── timingEngine.ts  # Timing validation
│   ├── scoringEngine.ts # Signal scoring
│   ├── proofEngine.ts   # Proof generation
│   └── types.ts         # TypeScript types
├── App.tsx             # Main app component
├── Verification.tsx    # Verification flow component
├── main.tsx            # React entry point
└── index.css           # Global styles
```

### Customization

- Modify challenge types in `liveness/challengeEngine.ts`
- Adjust scoring thresholds in `liveness/scoringEngine.ts`
- Customize UI in `Verification.tsx`
- Update branding/styles in `index.css` and component styles

## Troubleshooting

### Camera not working

- Ensure HTTPS in production (required for camera access)
- Check browser permissions
- Verify no other app is using the camera

### Verification failing

- Check lighting conditions
- Ensure face is fully visible
- Follow on-screen instructions carefully
- Check browser console for errors

### Build errors

```bash
# Clear node_modules and reinstall
rm -rf node_modules package-lock.json
npm install
```

## License

Proprietary - 54agent Technologies
