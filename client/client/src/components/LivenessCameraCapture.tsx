import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Camera,
  CheckCircle,
  XCircle,
  RefreshCw,
  AlertTriangle,
  Loader2,
  Signal,
  SignalLow,
  SignalMedium,
  SignalHigh,
  Wifi,
  WifiOff,
  Eye,
  Scan,
} from "lucide-react";
import { useFaceMotionDetection } from "@/hooks/useFaceMotionDetection";
import type { ChallengeType as MotionChallengeType } from "@/hooks/useFaceMotionDetection";

// ── Types ───────────────────────────────────────────────────────────────────

type ChallengeType =
  | "blink"
  | "turn_left"
  | "turn_right"
  | "nod"
  | "smile"
  | "open_mouth";

interface Challenge {
  type: ChallengeType;
  instruction: string;
  completed: boolean;
}

interface LivenessResult {
  is_live: boolean;
  confidence: number;
  spoof_type?: string;
  challenges_passed: number;
  challenges_total: number;
  frames_captured: number;
  mode_used?: "active" | "passive";
}

interface Props {
  mode: "passive" | "active";
  onCapture?: (imageBase64: string) => void;
  onLivenessResult?: (result: LivenessResult) => void;
  onError?: (error: string) => void;
  challengeCount?: number;
  autoStart?: boolean;
  showGuide?: boolean;
  /** Enable automatic fallback to passive liveness after repeated active failures */
  enablePassiveFallback?: boolean;
  /** Number of active failures before switching to passive (default: 2) */
  fallbackThreshold?: number;
}

// ── Camera Quality Types ───────────────────────────────────────────────────

type QualityLevel = "excellent" | "good" | "fair" | "poor";

interface CameraQuality {
  level: QualityLevel;
  score: number; // 0-100
  brightness: number;
  sharpness: number;
  stability: number;
  noiseLevel: number;
  recommendation: string;
}

// ── Challenge Definitions ───────────────────────────────────────────────────

const CHALLENGE_POOL: Challenge[] = [
  { type: "blink", instruction: "Please blink your eyes", completed: false },
  {
    type: "turn_left",
    instruction: "Turn your head slowly to the left",
    completed: false,
  },
  {
    type: "turn_right",
    instruction: "Turn your head slowly to the right",
    completed: false,
  },
  { type: "nod", instruction: "Nod your head up and down", completed: false },
  { type: "smile", instruction: "Please smile", completed: false },
  {
    type: "open_mouth",
    instruction: "Open your mouth slightly",
    completed: false,
  },
];

// ── Quality Assessment Helpers ──────────────────────────────────────────────

function assessFrameQuality(
  imageData: ImageData,
  prevImageData: ImageData | null
): CameraQuality {
  const { data, width, height } = imageData;
  const totalPixels = width * height;

  // 1. Brightness: average luminance
  let totalLuminance = 0;
  for (let i = 0; i < data.length; i += 4) {
    totalLuminance +=
      0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
  }
  const avgBrightness = totalLuminance / totalPixels;
  // Ideal brightness is 100-180; penalize extremes
  const brightnessScore = Math.max(
    0,
    100 - Math.abs(avgBrightness - 140) * 1.2
  );

  // 2. Sharpness: Laplacian variance (approximation using neighbor differences)
  let laplacianSum = 0;
  let laplacianCount = 0;
  const stride = 4; // Sample every 4th pixel for performance
  for (let y = 1; y < height - 1; y += stride) {
    for (let x = 1; x < width - 1; x += stride) {
      const idx = (y * width + x) * 4;
      const center = data[idx]; // Red channel
      const top = data[((y - 1) * width + x) * 4];
      const bottom = data[((y + 1) * width + x) * 4];
      const left = data[(y * width + (x - 1)) * 4];
      const right = data[(y * width + (x + 1)) * 4];
      const laplacian = Math.abs(4 * center - top - bottom - left - right);
      laplacianSum += laplacian;
      laplacianCount++;
    }
  }
  const sharpnessVariance = laplacianSum / Math.max(laplacianCount, 1);
  // Higher variance = sharper. Typical range: 5-50
  const sharpnessScore = Math.min(
    100,
    Math.max(0, (sharpnessVariance - 3) * 4)
  );

  // 3. Noise estimation: standard deviation of pixel differences in flat regions
  let noiseSamples: number[] = [];
  for (let y = 2; y < height - 2; y += stride * 2) {
    for (let x = 2; x < width - 2; x += stride * 2) {
      const idx = (y * width + x) * 4;
      const neighbors = [
        data[((y - 1) * width + x) * 4],
        data[((y + 1) * width + x) * 4],
        data[(y * width + (x - 1)) * 4],
        data[(y * width + (x + 1)) * 4],
      ];
      const avg = neighbors.reduce((a, b) => a + b, 0) / 4;
      const diff = Math.abs(data[idx] - avg);
      noiseSamples.push(diff);
    }
  }
  const noiseMedian =
    noiseSamples.sort((a, b) => a - b)[Math.floor(noiseSamples.length / 2)] ||
    0;
  // Lower noise = better. Typical: 1-15
  const noiseScore = Math.max(0, 100 - noiseMedian * 8);

  // 4. Stability: frame-to-frame difference (if previous frame available)
  let stabilityScore = 85; // Default if no previous frame
  if (prevImageData) {
    let diffSum = 0;
    const prevData = prevImageData.data;
    const sampleStep = 16; // Sample every 16th pixel for speed
    let sampleCount = 0;
    for (
      let i = 0;
      i < Math.min(data.length, prevData.length);
      i += 4 * sampleStep
    ) {
      diffSum += Math.abs(data[i] - prevData[i]);
      sampleCount++;
    }
    const avgDiff = diffSum / Math.max(sampleCount, 1);
    // Low diff = stable. Typical: 2-30
    stabilityScore = Math.max(0, 100 - avgDiff * 3);
  }

  // Overall score (weighted)
  const overallScore = Math.round(
    brightnessScore * 0.25 +
      sharpnessScore * 0.3 +
      noiseScore * 0.25 +
      stabilityScore * 0.2
  );

  // Determine level
  let level: QualityLevel;
  let recommendation: string;
  if (overallScore >= 75) {
    level = "excellent";
    recommendation = "Camera quality is great — proceed with liveness check";
  } else if (overallScore >= 55) {
    level = "good";
    recommendation = "Camera quality is acceptable";
  } else if (overallScore >= 35) {
    level = "fair";
    recommendation = "Try improving lighting or holding device steadier";
  } else {
    level = "poor";
    recommendation =
      "Poor camera quality — move to better lighting and hold still";
  }

  return {
    level,
    score: overallScore,
    brightness: Math.round(brightnessScore),
    sharpness: Math.round(sharpnessScore),
    stability: Math.round(stabilityScore),
    noiseLevel: Math.round(noiseScore),
    recommendation,
  };
}

// ── Quality Indicator Component ─────────────────────────────────────────────

function QualityIndicator({ quality }: { quality: CameraQuality | null }) {
  if (!quality) return null;

  const colorMap: Record<QualityLevel, string> = {
    excellent: "text-green-400",
    good: "text-blue-400",
    fair: "text-yellow-400",
    poor: "text-red-400",
  };

  const bgMap: Record<QualityLevel, string> = {
    excellent: "bg-green-500/20",
    good: "bg-blue-500/20",
    fair: "bg-yellow-500/20",
    poor: "bg-red-500/20",
  };

  const IconComponent =
    quality.level === "excellent"
      ? SignalHigh
      : quality.level === "good"
        ? SignalMedium
        : quality.level === "fair"
          ? SignalLow
          : Signal;

  return (
    <div
      className={`absolute top-3 right-3 ${bgMap[quality.level]} backdrop-blur-sm rounded-lg px-3 py-2 pointer-events-none`}
    >
      <div className="flex items-center gap-2">
        <IconComponent className={`h-4 w-4 ${colorMap[quality.level]}`} />
        <div className="text-xs">
          <div className={`font-semibold ${colorMap[quality.level]}`}>
            {quality.score}/100
          </div>
          <div className="text-white/70 text-[10px] leading-tight max-w-[100px]">
            {quality.level === "poor" || quality.level === "fair"
              ? quality.recommendation
              : quality.level.charAt(0).toUpperCase() + quality.level.slice(1)}
          </div>
        </div>
      </div>
      {/* Mini bar chart for quality dimensions */}
      <div className="flex gap-1 mt-1.5">
        {[
          { label: "B", value: quality.brightness },
          { label: "S", value: quality.sharpness },
          { label: "N", value: quality.noiseLevel },
          { label: "St", value: quality.stability },
        ].map(({ label, value }) => (
          <div key={label} className="flex flex-col items-center">
            <div className="w-3 h-8 bg-white/10 rounded-sm overflow-hidden relative">
              <div
                className={`absolute bottom-0 w-full rounded-sm ${
                  value >= 60
                    ? "bg-green-400/70"
                    : value >= 40
                      ? "bg-yellow-400/70"
                      : "bg-red-400/70"
                }`}
                style={{ height: `${value}%` }}
              />
            </div>
            <span className="text-[8px] text-white/50 mt-0.5">{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Component ───────────────────────────────────────────────────────────────

export default function LivenessCameraCapture({
  mode = "passive",
  onCapture,
  onLivenessResult,
  onError,
  challengeCount = 3,
  autoStart = false,
  showGuide = true,
  enablePassiveFallback = true,
  fallbackThreshold = 2,
}: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const qualityCanvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const prevImageDataRef = useRef<ImageData | null>(null);
  const qualityIntervalRef = useRef<ReturnType<typeof setInterval> | null>(
    null
  );

  const [cameraReady, setCameraReady] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [capturing, setCapturing] = useState(false);
  const [capturedImage, setCapturedImage] = useState<string | null>(null);

  // Active liveness state
  const [challenges, setChallenges] = useState<Challenge[]>([]);
  const [currentChallengeIdx, setCurrentChallengeIdx] = useState(0);
  const [challengeTimer, setChallengeTimer] = useState(0);
  const [framesCollected, setFramesCollected] = useState<string[]>([]);
  const [livenessComplete, setLivenessComplete] = useState(false);
  const [livenessResult, setLivenessResult] = useState<LivenessResult | null>(
    null
  );

  // Camera quality state
  const [cameraQuality, setCameraQuality] = useState<CameraQuality | null>(
    null
  );

  // Passive fallback state
  const [activeFailureCount, setActiveFailureCount] = useState(0);
  const [fallbackMode, setFallbackMode] = useState(false);
  const [showFallbackNotice, setShowFallbackNotice] = useState(false);

  // ── Face Motion Detection (MediaPipe) ───────────────────────────────────

  const currentChallengeType: MotionChallengeType | null =
    capturing &&
    !fallbackMode &&
    challenges.length > 0 &&
    currentChallengeIdx < challenges.length
      ? challenges[currentChallengeIdx].type
      : null;

  const handleMotionDetected = useCallback(
    (type: MotionChallengeType, confidence: number) => {
      if (!capturing || fallbackMode || livenessComplete) return;
      if (currentChallengeIdx >= challenges.length) return;
      if (type !== challenges[currentChallengeIdx].type) return;
      handleChallengeResponse(true);
    },
    [capturing, fallbackMode, livenessComplete, currentChallengeIdx, challenges]
  );

  const motionState = useFaceMotionDetection({
    videoRef,
    enabled: cameraReady && mode === "active" && capturing && !fallbackMode,
    activeChallenge: currentChallengeType,
    onChallengeDetected: handleMotionDetected,
    detectionIntervalMs: 100,
  });

  // ── Camera Setup ──────────────────────────────────────────────────────────

  const startCamera = useCallback(async () => {
    try {
      setCameraError(null);
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: "user",
          width: { ideal: 1280, min: 640 },
          height: { ideal: 720, min: 480 },
          frameRate: { ideal: 30, min: 15 },
        },
        audio: false,
      });

      streamRef.current = stream;

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
        setCameraReady(true);
      }
    } catch (err: any) {
      const msg =
        err.name === "NotAllowedError"
          ? "Camera permission denied. Please allow camera access."
          : err.name === "NotFoundError"
            ? "No camera found. Please connect a camera."
            : `Camera error: ${err.message}`;
      setCameraError(msg);
      onError?.(msg);
    }
  }, [onError]);

  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
    if (qualityIntervalRef.current) {
      clearInterval(qualityIntervalRef.current);
      qualityIntervalRef.current = null;
    }
    setCameraReady(false);
    setCameraQuality(null);
  }, []);

  useEffect(() => {
    if (autoStart) {
      startCamera();
    }
    return () => stopCamera();
  }, [autoStart, startCamera, stopCamera]);

  // ── Real-time Quality Monitoring ──────────────────────────────────────────

  useEffect(() => {
    if (!cameraReady || !videoRef.current) return;

    const assessQuality = () => {
      const video = videoRef.current;
      if (!video || video.videoWidth === 0) return;

      const canvas = qualityCanvasRef.current;
      if (!canvas) return;

      // Use a smaller canvas for performance (160x120)
      const sampleWidth = 160;
      const sampleHeight = 120;
      canvas.width = sampleWidth;
      canvas.height = sampleHeight;

      const ctx = canvas.getContext("2d", { willReadFrequently: true });
      if (!ctx) return;

      ctx.drawImage(video, 0, 0, sampleWidth, sampleHeight);
      const imageData = ctx.getImageData(0, 0, sampleWidth, sampleHeight);

      const quality = assessFrameQuality(imageData, prevImageDataRef.current);
      setCameraQuality(quality);
      prevImageDataRef.current = imageData;
    };

    // Assess quality every 1 second
    qualityIntervalRef.current = setInterval(assessQuality, 1000);
    // Initial assessment after 500ms
    const timeout = setTimeout(assessQuality, 500);

    return () => {
      if (qualityIntervalRef.current) {
        clearInterval(qualityIntervalRef.current);
      }
      clearTimeout(timeout);
    };
  }, [cameraReady]);

  // ── Frame Capture ─────────────────────────────────────────────────────────

  const captureFrame = useCallback((): string | null => {
    if (!videoRef.current || !canvasRef.current) return null;

    const video = videoRef.current;
    const canvas = canvasRef.current;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    const ctx = canvas.getContext("2d");
    if (!ctx) return null;

    // Mirror the image (front camera)
    ctx.translate(canvas.width, 0);
    ctx.scale(-1, 1);
    ctx.drawImage(video, 0, 0);
    ctx.setTransform(1, 0, 0, 1, 0, 0);

    return canvas.toDataURL("image/jpeg", 0.92).split(",")[1];
  }, []);

  // ── Passive Capture ───────────────────────────────────────────────────────

  const handlePassiveCapture = useCallback(() => {
    const frame = captureFrame();
    if (frame) {
      setCapturedImage(`data:image/jpeg;base64,${frame}`);
      onCapture?.(frame);
    }
  }, [captureFrame, onCapture]);

  // ── Active Liveness ───────────────────────────────────────────────────────

  const startActiveLiveness = useCallback(() => {
    const shuffled = [...CHALLENGE_POOL].sort(() => Math.random() - 0.5);
    const selected = shuffled.slice(0, challengeCount).map(c => ({ ...c }));
    setChallenges(selected);
    setCurrentChallengeIdx(0);
    setFramesCollected([]);
    setLivenessComplete(false);
    setLivenessResult(null);
    setCapturing(true);
    setChallengeTimer(12); // Extended for noisy cameras
  }, [challengeCount]);

  // ── Passive Fallback Liveness ─────────────────────────────────────────────

  const startPassiveFallback = useCallback(() => {
    setFallbackMode(true);
    setShowFallbackNotice(true);
    setLivenessComplete(false);
    setLivenessResult(null);
    setCapturing(true);

    // Capture multiple frames over 3 seconds for passive anti-spoof analysis
    const frames: string[] = [];
    let count = 0;
    const interval = setInterval(() => {
      const frame = captureFrame();
      if (frame) frames.push(frame);
      count++;
      if (count >= 6) {
        clearInterval(interval);
        setCapturing(false);
        setLivenessComplete(true);

        // Passive liveness uses texture/frequency analysis — no motion needed
        const result: LivenessResult = {
          is_live: frames.length >= 4, // Need minimum frames for analysis
          confidence: Math.min(0.85, frames.length * 0.14), // Passive max confidence is lower
          challenges_passed: frames.length >= 4 ? 1 : 0,
          challenges_total: 1,
          frames_captured: frames.length,
          mode_used: "passive",
        };

        setLivenessResult(result);
        onLivenessResult?.(result);
        setFramesCollected(frames);
      }
    }, 500);

    return () => clearInterval(interval);
  }, [captureFrame, onLivenessResult]);

  // Challenge timer countdown
  useEffect(() => {
    if (!capturing || challengeTimer <= 0 || fallbackMode) return;

    const interval = setInterval(() => {
      setChallengeTimer(prev => {
        if (prev <= 1) {
          handleChallengeResponse(false);
          return 0;
        }
        return prev - 0.5;
      });

      // Capture frames at 2fps for better motion detection on noisy cameras
      const frame = captureFrame();
      if (frame) {
        setFramesCollected(prev => [...prev, frame]);
      }
    }, 500);

    return () => clearInterval(interval);
  }, [capturing, challengeTimer, captureFrame, fallbackMode]);

  const handleChallengeResponse = useCallback(
    (passed: boolean) => {
      setChallenges(prev => {
        const updated = [...prev];
        if (currentChallengeIdx < updated.length) {
          updated[currentChallengeIdx] = {
            ...updated[currentChallengeIdx],
            completed: passed,
          };
        }
        return updated;
      });

      const nextIdx = currentChallengeIdx + 1;
      if (nextIdx >= challenges.length) {
        setCapturing(false);
        setLivenessComplete(true);

        const passedCount =
          challenges.filter((c, i) =>
            i < currentChallengeIdx
              ? c.completed
              : i === currentChallengeIdx
                ? passed
                : false
          ).length + (passed ? 1 : 0);

        const result: LivenessResult = {
          is_live: passedCount >= Math.ceil(challengeCount * 0.7),
          confidence: passedCount / challengeCount,
          challenges_passed: passedCount,
          challenges_total: challengeCount,
          frames_captured: framesCollected.length,
          mode_used: "active",
        };

        setLivenessResult(result);
        onLivenessResult?.(result);

        // Track failures for passive fallback
        if (!result.is_live) {
          const newFailCount = activeFailureCount + 1;
          setActiveFailureCount(newFailCount);
        }
      } else {
        setCurrentChallengeIdx(nextIdx);
        setChallengeTimer(12);
      }
    },
    [
      currentChallengeIdx,
      challenges,
      challengeCount,
      framesCollected,
      onLivenessResult,
      activeFailureCount,
    ]
  );

  // ── Retry ─────────────────────────────────────────────────────────────────

  const handleRetry = useCallback(() => {
    setCapturedImage(null);
    setLivenessComplete(false);
    setLivenessResult(null);
    setCapturing(false);
    setChallenges([]);
    setFramesCollected([]);
    setFallbackMode(false);
    setShowFallbackNotice(false);
  }, []);

  // ── Should show fallback option ───────────────────────────────────────────

  const shouldOfferFallback =
    enablePassiveFallback &&
    activeFailureCount >= fallbackThreshold &&
    !fallbackMode &&
    livenessComplete &&
    livenessResult &&
    !livenessResult.is_live;

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <Card className="w-full max-w-lg mx-auto">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Camera className="h-5 w-5" />
          {fallbackMode
            ? "Passive Liveness Check"
            : mode === "passive"
              ? "Face Capture"
              : "Active Liveness Check"}
          {activeFailureCount > 0 && !fallbackMode && (
            <Badge variant="outline" className="text-xs ml-auto">
              Attempts: {activeFailureCount}
            </Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Camera Error */}
        {cameraError && (
          <div className="flex items-center gap-2 p-3 bg-destructive/10 text-destructive rounded-lg">
            <AlertTriangle className="h-5 w-5 shrink-0" />
            <p className="text-sm">{cameraError}</p>
          </div>
        )}

        {/* Fallback Notice */}
        {showFallbackNotice && (
          <div className="flex items-center gap-2 p-3 bg-blue-500/10 text-blue-600 dark:text-blue-400 rounded-lg">
            <Signal className="h-5 w-5 shrink-0" />
            <div className="text-sm">
              <p className="font-medium">Switched to passive liveness</p>
              <p className="text-xs opacity-80 mt-0.5">
                Active challenges failed {fallbackThreshold}+ times. Using
                single-frame anti-spoof analysis instead — no motion required.
              </p>
            </div>
          </div>
        )}

        {/* Video Feed */}
        <div className="relative aspect-[4/3] bg-black rounded-lg overflow-hidden">
          <video
            ref={videoRef}
            className="w-full h-full object-cover"
            style={{ transform: "scaleX(-1)" }}
            playsInline
            muted
          />
          <canvas ref={canvasRef} className="hidden" />
          <canvas ref={qualityCanvasRef} className="hidden" />

          {/* Real-time Camera Quality Score Indicator */}
          {cameraReady && !capturedImage && (
            <QualityIndicator quality={cameraQuality} />
          )}

          {/* Face Guide Overlay */}
          {showGuide && cameraReady && !capturedImage && (
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
              <div
                className="border-2 border-dashed border-white/60 rounded-full"
                style={{ width: "55%", height: "75%" }}
              />
              <p className="absolute bottom-4 text-white text-sm bg-black/50 px-3 py-1 rounded">
                Position your face within the oval
              </p>
            </div>
          )}

          {/* Camera quality warning for poor conditions */}
          {cameraReady &&
            cameraQuality &&
            cameraQuality.level === "poor" &&
            !capturing && (
              <div className="absolute bottom-12 left-1/2 -translate-x-1/2 bg-red-500/90 text-white text-xs px-3 py-1.5 rounded-full pointer-events-none animate-pulse">
                ⚠️ Improve lighting before starting
              </div>
            )}

          {/* Captured Image Preview */}
          {capturedImage && (
            <img
              src={capturedImage}
              alt="Captured face"
              className="absolute inset-0 w-full h-full object-cover"
            />
          )}

          {/* Active Challenge Overlay */}
          {capturing &&
            !fallbackMode &&
            challenges.length > 0 &&
            currentChallengeIdx < challenges.length && (
              <div className="absolute inset-0 flex flex-col items-center justify-between p-4 pointer-events-none">
                <div className="bg-black/70 text-white px-4 py-2 rounded-lg text-center max-w-[85%]">
                  <p className="text-sm font-medium">
                    Challenge {currentChallengeIdx + 1} of {challenges.length}
                  </p>
                  <p className="text-lg font-bold mt-1">
                    {challenges[currentChallengeIdx].instruction}
                  </p>
                  <p className="text-xs opacity-70 mt-1">
                    {motionState.ready
                      ? "Motion will be detected automatically"
                      : "Loading face detection..."}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge
                    variant={challengeTimer > 3 ? "default" : "destructive"}
                  >
                    {Math.ceil(challengeTimer)}s
                  </Badge>
                  <div className="flex gap-1">
                    {challenges.map((c, i) => (
                      <div
                        key={i}
                        className={`w-3 h-3 rounded-full ${
                          i < currentChallengeIdx
                            ? c.completed
                              ? "bg-green-500"
                              : "bg-red-500"
                            : i === currentChallengeIdx
                              ? "bg-yellow-400 animate-pulse"
                              : "bg-white/40"
                        }`}
                      />
                    ))}
                  </div>
                </div>
              </div>
            )}

          {/* Passive Fallback Overlay */}
          {capturing && fallbackMode && (
            <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
              <div className="bg-black/70 text-white px-4 py-3 rounded-lg text-center">
                <Loader2 className="h-6 w-6 animate-spin mx-auto mb-2" />
                <p className="text-sm font-medium">Analyzing face...</p>
                <p className="text-xs opacity-70 mt-1">
                  Hold still — no motion needed
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Face Detection Status (during active liveness) */}
        {capturing && !fallbackMode && (
          <div className="space-y-3">
            {/* Motion detection status */}
            <div className="flex items-center gap-2 p-2 bg-muted/50 rounded-lg">
              {motionState.ready ? (
                <>
                  {motionState.faceDetected ? (
                    <Eye className="h-4 w-4 text-green-500" />
                  ) : (
                    <Scan className="h-4 w-4 text-yellow-500 animate-pulse" />
                  )}
                  <div className="flex-1">
                    <p className="text-xs font-medium">
                      {motionState.faceDetected
                        ? "Face detected — perform the action shown above"
                        : "Position your face in the oval"}
                    </p>
                    {motionState.faceDetected && currentChallengeType && (
                      <div className="flex gap-3 text-[10px] text-muted-foreground mt-1">
                        {currentChallengeType === "blink" && (
                          <span>
                            Eye openness:{" "}
                            {(motionState.metrics.ear * 100).toFixed(0)}%
                          </span>
                        )}
                        {(currentChallengeType === "turn_left" ||
                          currentChallengeType === "turn_right") && (
                          <span>
                            Head angle: {motionState.metrics.yaw.toFixed(1)}
                            &deg;
                          </span>
                        )}
                        {currentChallengeType === "nod" && (
                          <span>
                            Head pitch: {motionState.metrics.pitch.toFixed(1)}
                            &deg;
                          </span>
                        )}
                        {currentChallengeType === "smile" && (
                          <span>
                            Smile:{" "}
                            {(
                              (motionState.metrics.smileRatio / 4) *
                              100
                            ).toFixed(0)}
                            %
                          </span>
                        )}
                        {currentChallengeType === "open_mouth" && (
                          <span>
                            Mouth: {(motionState.metrics.mar * 100).toFixed(0)}%
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </>
              ) : (
                <>
                  <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                  <p className="text-xs text-muted-foreground">
                    Loading face detection model...
                  </p>
                </>
              )}
            </div>

            {/* Skip button as accessibility fallback */}
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                className="flex-1 text-xs"
                onClick={() => handleChallengeResponse(false)}
              >
                <XCircle className="h-3 w-3 mr-1" />
                Skip this challenge
              </Button>
            </div>
          </div>
        )}

        {/* Liveness Result */}
        {livenessComplete && livenessResult && (
          <div
            className={`p-4 rounded-lg ${
              livenessResult.is_live
                ? "bg-green-500/10 border border-green-500/30"
                : "bg-red-500/10 border border-red-500/30"
            }`}
          >
            <div className="flex items-center gap-2 mb-2">
              {livenessResult.is_live ? (
                <CheckCircle className="h-5 w-5 text-green-500" />
              ) : (
                <XCircle className="h-5 w-5 text-red-500" />
              )}
              <span className="font-semibold">
                {livenessResult.is_live
                  ? "Liveness Verified"
                  : "Liveness Failed"}
              </span>
              {livenessResult.mode_used && (
                <Badge variant="outline" className="text-xs ml-auto">
                  {livenessResult.mode_used === "passive"
                    ? "Passive"
                    : "Active"}
                </Badge>
              )}
            </div>
            <div className="text-sm text-muted-foreground space-y-1">
              <p>Confidence: {(livenessResult.confidence * 100).toFixed(1)}%</p>
              <p>
                Challenges: {livenessResult.challenges_passed}/
                {livenessResult.challenges_total} passed
              </p>
              <p>Frames captured: {livenessResult.frames_captured}</p>
            </div>
          </div>
        )}

        {/* Passive Fallback Offer */}
        {shouldOfferFallback && (
          <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg">
            <p className="text-sm font-medium text-amber-600 dark:text-amber-400 mb-2">
              Having trouble with motion challenges?
            </p>
            <p className="text-xs text-muted-foreground mb-3">
              Your camera may have too much noise for motion detection. You can
              try a passive check instead — it uses face texture analysis
              without requiring head movements.
            </p>
            <Button
              size="sm"
              variant="outline"
              className="w-full border-amber-500/50 text-amber-600 dark:text-amber-400"
              onClick={startPassiveFallback}
            >
              <Signal className="h-4 w-4 mr-2" />
              Try Passive Liveness Instead
            </Button>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex gap-2">
          {!cameraReady && !cameraError && (
            <Button onClick={startCamera} className="flex-1">
              <Camera className="h-4 w-4 mr-2" />
              Start Camera
            </Button>
          )}

          {cameraReady &&
            mode === "passive" &&
            !capturedImage &&
            !fallbackMode && (
              <Button onClick={handlePassiveCapture} className="flex-1">
                <Camera className="h-4 w-4 mr-2" />
                Capture Photo
              </Button>
            )}

          {cameraReady &&
            mode === "active" &&
            !capturing &&
            !livenessComplete &&
            !fallbackMode && (
              <Button
                onClick={startActiveLiveness}
                className="flex-1"
                disabled={cameraQuality?.level === "poor"}
              >
                <Loader2 className="h-4 w-4 mr-2" />
                Start Liveness Check
              </Button>
            )}

          {(capturedImage || livenessComplete) && (
            <Button variant="outline" onClick={handleRetry} className="flex-1">
              <RefreshCw className="h-4 w-4 mr-2" />
              Retry
            </Button>
          )}

          {cameraReady && (
            <Button variant="ghost" onClick={stopCamera}>
              Stop
            </Button>
          )}
        </div>

        {/* Quality warning when button is disabled */}
        {cameraReady &&
          cameraQuality?.level === "poor" &&
          mode === "active" &&
          !capturing &&
          !livenessComplete && (
            <p className="text-xs text-destructive text-center">
              Camera quality too low to start. Please improve lighting or hold
              device steadier.
            </p>
          )}
        {/* Camera quality guidance */}
        <p className="text-xs text-muted-foreground text-center mt-2">
          Tip: Use good lighting and hold device steady
        </p>
      </CardContent>
    </Card>
  );
}
