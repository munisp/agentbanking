/**
 * useFaceMotionDetection — real-time face landmark detection via MediaPipe FaceLandmarker.
 *
 * Detects facial movements for active liveness challenges:
 *   blink       — Eye Aspect Ratio (EAR) drops below threshold
 *   turn_left   — face yaw angle exceeds threshold (nose moves right in mirrored view)
 *   turn_right  — face yaw angle exceeds threshold (nose moves left in mirrored view)
 *   nod         — nose tip Y oscillates (pitch change)
 *   smile       — mouth width/height ratio increases
 *   open_mouth  — Mouth Aspect Ratio (MAR) exceeds threshold
 */

import { useCallback, useEffect, useRef, useState } from "react";

// ── Types ────────────────────────────────────────────────────────────────────

export type ChallengeType =
  | "blink"
  | "turn_left"
  | "turn_right"
  | "nod"
  | "smile"
  | "open_mouth";

export interface MotionState {
  /** Whether face detection model is loaded and ready */
  ready: boolean;
  /** Whether a face is currently detected in the frame */
  faceDetected: boolean;
  /** Current detected challenge (if any) */
  detectedChallenge: ChallengeType | null;
  /** Confidence of the current detection (0-1) */
  confidence: number;
  /** Error message if model failed to load */
  error: string | null;
  /** Real-time metrics for debugging/display */
  metrics: {
    ear: number; // Eye Aspect Ratio (blink)
    mar: number; // Mouth Aspect Ratio (open mouth)
    yaw: number; // Head yaw angle in degrees
    pitch: number; // Head pitch angle in degrees
    smileRatio: number; // Mouth width / height ratio
  };
}

interface UseFaceMotionDetectionOptions {
  videoRef: React.RefObject<HTMLVideoElement | null>;
  enabled: boolean;
  /** Which challenge to actively look for (null = detect any) */
  activeChallenge?: ChallengeType | null;
  /** Called when a challenge motion is detected */
  onChallengeDetected?: (type: ChallengeType, confidence: number) => void;
  /** Detection interval in ms (default: 100 = ~10fps) */
  detectionIntervalMs?: number;
}

// ── Landmark indices (MediaPipe 478-point face mesh) ─────────────────────────

// Left eye landmarks (upper/lower lid)
const LEFT_EYE_UPPER = [159, 145, 133, 173];
const LEFT_EYE_LOWER = [144, 163, 153, 154];
const LEFT_EYE_INNER = 133;
const LEFT_EYE_OUTER = 33;

// Right eye landmarks
const RIGHT_EYE_UPPER = [386, 374, 362, 398];
const RIGHT_EYE_LOWER = [373, 390, 380, 381];
const RIGHT_EYE_INNER = 362;
const RIGHT_EYE_OUTER = 263;

// Mouth landmarks
const MOUTH_LEFT = 61;
const MOUTH_RIGHT = 291;
const MOUTH_TOP = 13;
const MOUTH_BOTTOM = 14;
const UPPER_LIP_TOP = 0;
const LOWER_LIP_BOTTOM = 17;

// Nose tip for head pose estimation
const NOSE_TIP = 1;
const FOREHEAD = 10;
const CHIN = 152;
const LEFT_CHEEK = 234;
const RIGHT_CHEEK = 454;

// ── Geometry helpers ─────────────────────────────────────────────────────────

interface Point3D {
  x: number;
  y: number;
  z: number;
}

function distance(a: Point3D, b: Point3D): number {
  return Math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2);
}

function computeEAR(
  landmarks: Point3D[],
  upperIndices: number[],
  lowerIndices: number[],
  innerIdx: number,
  outerIdx: number
): number {
  // EAR = (|p2-p6| + |p3-p5|) / (2 * |p1-p4|)
  const horizontal = distance(landmarks[innerIdx], landmarks[outerIdx]);
  if (horizontal < 0.001) return 0.3;

  let verticalSum = 0;
  const pairs = Math.min(upperIndices.length, lowerIndices.length);
  for (let i = 0; i < pairs; i++) {
    verticalSum += distance(
      landmarks[upperIndices[i]],
      landmarks[lowerIndices[i]]
    );
  }
  return verticalSum / (pairs * horizontal);
}

function computeMAR(landmarks: Point3D[]): number {
  const horizontal = distance(landmarks[MOUTH_LEFT], landmarks[MOUTH_RIGHT]);
  if (horizontal < 0.001) return 0;
  const vertical = distance(landmarks[MOUTH_TOP], landmarks[MOUTH_BOTTOM]);
  return vertical / horizontal;
}

function computeSmileRatio(landmarks: Point3D[]): number {
  const mouthWidth = distance(landmarks[MOUTH_LEFT], landmarks[MOUTH_RIGHT]);
  const lipHeight = distance(
    landmarks[UPPER_LIP_TOP],
    landmarks[LOWER_LIP_BOTTOM]
  );
  if (lipHeight < 0.001) return 1;
  return mouthWidth / lipHeight;
}

function estimateHeadYaw(landmarks: Point3D[]): number {
  // Yaw: compare nose-to-left-cheek vs nose-to-right-cheek distances
  const nose = landmarks[NOSE_TIP];
  const leftDist = distance(nose, landmarks[LEFT_CHEEK]);
  const rightDist = distance(nose, landmarks[RIGHT_CHEEK]);
  const total = leftDist + rightDist;
  if (total < 0.001) return 0;
  // Ratio: 0.5 = centered, >0.5 = turned right, <0.5 = turned left
  const ratio = leftDist / total;
  return (ratio - 0.5) * 120; // Approximate degrees (-30 to +30 range)
}

function estimateHeadPitch(landmarks: Point3D[]): number {
  // Pitch: compare nose-to-forehead vs nose-to-chin distances
  const nose = landmarks[NOSE_TIP];
  const foreheadDist = distance(nose, landmarks[FOREHEAD]);
  const chinDist = distance(nose, landmarks[CHIN]);
  const total = foreheadDist + chinDist;
  if (total < 0.001) return 0;
  const ratio = foreheadDist / total;
  return (ratio - 0.5) * 100; // Approximate degrees
}

// ── Thresholds ───────────────────────────────────────────────────────────────

const THRESHOLDS = {
  blink: { earBelow: 0.21, minDuration: 80 }, // EAR must drop below 0.21
  turn_left: { yawBelow: -12 }, // Head turned left > 12 degrees
  turn_right: { yawAbove: 12 }, // Head turned right > 12 degrees
  nod: { pitchChange: 8 }, // Pitch must change by 8+ degrees
  smile: { smileRatioAbove: 3.2 }, // Mouth width/height ratio > 3.2
  open_mouth: { marAbove: 0.45 }, // Mouth Aspect Ratio > 0.45
};

// Confirmation: require detection for N consecutive frames to reduce false positives
const CONFIRM_FRAMES = 3;

// ── Hook ─────────────────────────────────────────────────────────────────────

export function useFaceMotionDetection({
  videoRef,
  enabled,
  activeChallenge = null,
  onChallengeDetected,
  detectionIntervalMs = 100,
}: UseFaceMotionDetectionOptions): MotionState {
  const [state, setState] = useState<MotionState>({
    ready: false,
    faceDetected: false,
    detectedChallenge: null,
    confidence: 0,
    error: null,
    metrics: { ear: 0, mar: 0, yaw: 0, pitch: 0, smileRatio: 0 },
  });

  const landmarkerRef = useRef<any>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const confirmCountRef = useRef<Record<string, number>>({});
  const baselinePitchRef = useRef<number | null>(null);
  const pitchHistoryRef = useRef<number[]>([]);
  const baselineEarRef = useRef<number | null>(null);
  const detectedRef = useRef(false);

  // Load MediaPipe FaceLandmarker
  useEffect(() => {
    if (!enabled) return;

    let cancelled = false;

    async function loadModel() {
      try {
        const vision = await import("@mediapipe/tasks-vision");
        const { FaceLandmarker, FilesetResolver } = vision;

        const filesetResolver = await FilesetResolver.forVisionTasks(
          "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@latest/wasm"
        );

        const landmarker = await FaceLandmarker.createFromOptions(
          filesetResolver,
          {
            baseOptions: {
              modelAssetPath:
                "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
              delegate: "GPU",
            },
            runningMode: "VIDEO",
            numFaces: 1,
            minFaceDetectionConfidence: 0.5,
            minTrackingConfidence: 0.5,
            outputFaceBlendshapes: false,
            outputFacialTransformationMatrixes: false,
          }
        );

        if (!cancelled) {
          landmarkerRef.current = landmarker;
          setState(s => ({ ...s, ready: true, error: null }));
        }
      } catch (err: any) {
        if (!cancelled) {
          // Try CPU fallback if GPU fails
          try {
            const vision = await import("@mediapipe/tasks-vision");
            const { FaceLandmarker, FilesetResolver } = vision;

            const filesetResolver = await FilesetResolver.forVisionTasks(
              "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@latest/wasm"
            );

            const landmarker = await FaceLandmarker.createFromOptions(
              filesetResolver,
              {
                baseOptions: {
                  modelAssetPath:
                    "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
                  delegate: "CPU",
                },
                runningMode: "VIDEO",
                numFaces: 1,
                minFaceDetectionConfidence: 0.5,
                minTrackingConfidence: 0.5,
              }
            );

            if (!cancelled) {
              landmarkerRef.current = landmarker;
              setState(s => ({ ...s, ready: true, error: null }));
            }
          } catch (cpuErr: any) {
            if (!cancelled) {
              setState(s => ({
                ...s,
                error: `Face detection failed to load: ${cpuErr.message}`,
              }));
            }
          }
        }
      }
    }

    loadModel();

    return () => {
      cancelled = true;
      if (landmarkerRef.current) {
        landmarkerRef.current.close();
        landmarkerRef.current = null;
      }
    };
  }, [enabled]);

  // Reset detection state when active challenge changes
  useEffect(() => {
    confirmCountRef.current = {};
    detectedRef.current = false;
    baselinePitchRef.current = null;
    pitchHistoryRef.current = [];
  }, [activeChallenge]);

  // Run detection loop
  useEffect(() => {
    if (!enabled || !state.ready || !landmarkerRef.current) return;

    const detect = () => {
      const video = videoRef.current;
      const landmarker = landmarkerRef.current;
      if (!video || !landmarker || video.readyState < 2) return;

      try {
        const result = landmarker.detectForVideo(video, performance.now());

        if (!result.faceLandmarks || result.faceLandmarks.length === 0) {
          setState(s => ({
            ...s,
            faceDetected: false,
            detectedChallenge: null,
            confidence: 0,
          }));
          return;
        }

        const landmarks: Point3D[] = result.faceLandmarks[0];

        // Compute metrics
        const leftEAR = computeEAR(
          landmarks,
          LEFT_EYE_UPPER,
          LEFT_EYE_LOWER,
          LEFT_EYE_INNER,
          LEFT_EYE_OUTER
        );
        const rightEAR = computeEAR(
          landmarks,
          RIGHT_EYE_UPPER,
          RIGHT_EYE_LOWER,
          RIGHT_EYE_INNER,
          RIGHT_EYE_OUTER
        );
        const ear = (leftEAR + rightEAR) / 2;
        const mar = computeMAR(landmarks);
        const yaw = estimateHeadYaw(landmarks);
        const pitch = estimateHeadPitch(landmarks);
        const smileRatio = computeSmileRatio(landmarks);

        // Set baseline EAR on first detection (open eyes)
        if (baselineEarRef.current === null && ear > 0.22) {
          baselineEarRef.current = ear;
        }

        // Track pitch history for nod detection
        pitchHistoryRef.current.push(pitch);
        if (pitchHistoryRef.current.length > 30) {
          pitchHistoryRef.current.shift();
        }
        if (baselinePitchRef.current === null) {
          baselinePitchRef.current = pitch;
        }

        const metrics = { ear, mar, yaw, pitch, smileRatio };

        // Detect challenges
        let detected: ChallengeType | null = null;
        let conf = 0;

        const challengesToCheck = activeChallenge
          ? [activeChallenge]
          : ([
              "blink",
              "turn_left",
              "turn_right",
              "nod",
              "smile",
              "open_mouth",
            ] as ChallengeType[]);

        for (const ch of challengesToCheck) {
          const result = checkChallenge(ch, metrics);
          if (result.detected) {
            detected = ch;
            conf = result.confidence;
            break;
          }
        }

        // Confirmation: require CONFIRM_FRAMES consecutive detections
        if (detected) {
          const key = detected;
          confirmCountRef.current[key] =
            (confirmCountRef.current[key] || 0) + 1;

          if (
            confirmCountRef.current[key] >= CONFIRM_FRAMES &&
            !detectedRef.current
          ) {
            detectedRef.current = true;
            onChallengeDetected?.(detected, conf);
            setState(s => ({
              ...s,
              faceDetected: true,
              detectedChallenge: detected,
              confidence: conf,
              metrics,
            }));
            return;
          }
        } else {
          // Reset all counters if nothing detected
          confirmCountRef.current = {};
        }

        setState(s => ({
          ...s,
          faceDetected: true,
          detectedChallenge: detectedRef.current ? s.detectedChallenge : null,
          confidence: detectedRef.current ? s.confidence : 0,
          metrics,
        }));
      } catch {
        // Silently ignore detection errors (e.g. video not ready)
      }
    };

    intervalRef.current = setInterval(detect, detectionIntervalMs);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [
    enabled,
    state.ready,
    activeChallenge,
    onChallengeDetected,
    detectionIntervalMs,
    videoRef,
  ]);

  return state;
}

// ── Challenge detection logic ────────────────────────────────────────────────

function checkChallenge(
  type: ChallengeType,
  metrics: MotionState["metrics"]
): { detected: boolean; confidence: number } {
  switch (type) {
    case "blink":
      if (metrics.ear < THRESHOLDS.blink.earBelow) {
        const conf = Math.min(
          1,
          (THRESHOLDS.blink.earBelow - metrics.ear) / 0.08
        );
        return { detected: true, confidence: conf };
      }
      return { detected: false, confidence: 0 };

    case "turn_left":
      if (metrics.yaw < THRESHOLDS.turn_left.yawBelow) {
        const conf = Math.min(1, Math.abs(metrics.yaw) / 25);
        return { detected: true, confidence: conf };
      }
      return { detected: false, confidence: 0 };

    case "turn_right":
      if (metrics.yaw > THRESHOLDS.turn_right.yawAbove) {
        const conf = Math.min(1, metrics.yaw / 25);
        return { detected: true, confidence: conf };
      }
      return { detected: false, confidence: 0 };

    case "nod":
      if (Math.abs(metrics.pitch) > THRESHOLDS.nod.pitchChange) {
        const conf = Math.min(1, Math.abs(metrics.pitch) / 15);
        return { detected: true, confidence: conf };
      }
      return { detected: false, confidence: 0 };

    case "smile":
      if (metrics.smileRatio > THRESHOLDS.smile.smileRatioAbove) {
        const conf = Math.min(1, (metrics.smileRatio - 2.5) / 2);
        return { detected: true, confidence: conf };
      }
      return { detected: false, confidence: 0 };

    case "open_mouth":
      if (metrics.mar > THRESHOLDS.open_mouth.marAbove) {
        const conf = Math.min(1, metrics.mar / 0.7);
        return { detected: true, confidence: conf };
      }
      return { detected: false, confidence: 0 };

    default:
      return { detected: false, confidence: 0 };
  }
}

export default useFaceMotionDetection;
