import { useCallback, useEffect, useRef, useState } from "react";
import {
  addToBuffer,
  buildProof,
  captureFrame,
  frameDiff,
  generateChallenge,
  generateProofReport,
  getAverageBrightness,
  getChallengeInstruction,
  hashProof,
  initCamera,
  motionScore,
  scoreEngine,
  stopCamera,
  verifyChallengeResponse,
  type ChallengeType,
  type FrameData,
  type LivenessProof,
  type SignalInputs,
  type VerificationStatus,
} from "./liveness/index";

// API Configuration
const API_BASE_URL =
  import.meta.env.VITE_VERIFICATION_API_URL ||
  "https://54agent.upi.dev/verification";
const API_KEY = import.meta.env.VITE_KYC_FLOW_API_KEY || "";
const FALLBACK_KYC_API_KEY = "Zr6lIvOEuGDlzlDyV+/dEDcUX7cChZKs";

export default function Verification() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const documentVideoRef = useRef<HTMLVideoElement>(null);
  const documentCanvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const documentStreamRef = useRef<MediaStream | null>(null);
  const animationFrameRef = useRef<number | null>(null);

  // Get URL parameters
  const params = new URLSearchParams(window.location.search);
  const verification_id = params.get("verification_id") || "";
  const metadata = params.get("metadata") || "{}";

  const [status, setStatus] = useState<VerificationStatus>("IDLE");
  const [challenge, setChallenge] = useState<ChallengeType | null>(null);
  const [challenges, setChallenges] = useState<ChallengeType[]>([]);
  const [currentChallengeIndex, setCurrentChallengeIndex] = useState(0);
  const [progress, setProgress] = useState(0);
  const [proof, setProof] = useState<LivenessProof | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [countdown, setCountdown] = useState<number>(3);
  const [challengeSuccess, setChallengeSuccess] = useState<boolean>(false);
  const [debugMotion, setDebugMotion] = useState<number>(0);
  const [debugAvgMotion, setDebugAvgMotion] = useState<number>(0);
  const [documentStep, setDocumentStep] = useState<
    "idle" | "front" | "back" | "complete"
  >("idle");
  const [frontDocument, setFrontDocument] = useState<string | null>(null);
  const [backDocument, setBackDocument] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Frame buffers
  const frameBufferRef = useRef<FrameData[]>([]);
  const prevFrameRef = useRef<ImageData | null>(null);
  const motionHistoryRef = useRef<number[]>([]);
  const diffHistoryRef = useRef<number[]>([]);
  const brightnessHistoryRef = useRef<number[]>([]);

  console.log(submitting);
  console.log(debugMotion, debugAvgMotion);

  // Challenge tracking
  const challengeStartRef = useRef<number>(0);
  const challengeDetectedRef = useRef<boolean>(false);
  const challengeResponseTimesRef = useRef<number[]>([]);
  const allChallengesPassedRef = useRef<boolean>(false);
  const passedChallengesCountRef = useRef<number>(0);
  const totalChallengesRef = useRef<number>(4); // Store total count
  const noiseFloorRef = useRef<number>(0);
  const noiseCalibrationRef = useRef<number[]>([]);

  const submitVerification = async (livenessProof: LivenessProof) => {
    try {
      setSubmitting(true);

      // Validate verification_id exists
      if (!verification_id || verification_id.trim() === "") {
        throw new Error(
          "Invalid verification session. Please use a valid verification URL.",
        );
      }

      // Get selfie image from first frame
      let selfieImage = "";
      if (frameBufferRef.current.length > 0 && frameBufferRef.current[0]) {
        // Convert ImageData to base64 data URL
        const canvas = document.createElement("canvas");
        const frameData = frameBufferRef.current[0].imageData;
        canvas.width = frameData.width;
        canvas.height = frameData.height;
        const ctx = canvas.getContext("2d");
        if (ctx) {
          ctx.putImageData(frameData, 0, 0);
          selfieImage = canvas.toDataURL("image/jpeg", 0.8);
        }
      }

      // Prepare payload for verification service
      const payload = {
        endUserInfo: {
          id: verification_id,
        },
        document:
          frontDocument && backDocument
            ? {
                type: "id_card",
                country: "NG",
                frontImage: frontDocument,
                backImage: backDocument,
              }
            : undefined,
        selfie: selfieImage
          ? {
              image: selfieImage,
            }
          : undefined,
        livenessProof: {
          sessionId: livenessProof.sessionId,
          timestamp: livenessProof.timestamp,
          confidence: livenessProof.confidence,
          verdict: livenessProof.verdict,
          signals: livenessProof.signals,
          hash: livenessProof.hash,
        },
        metadata:
          metadata && metadata !== "{}" ? JSON.parse(metadata) : undefined,
      };

      const headers: Record<string, string> = {
        "Content-Type": "application/json",
      };

      // Add API key as Authorization header. Prefer env, then URL, then fallback.
      const apiKeyFromUrl = params.get("api_key") || "";
      const resolvedApiKey = (API_KEY || apiKeyFromUrl || FALLBACK_KYC_API_KEY).trim();
      if (!resolvedApiKey) {
        throw new Error("Missing KYC API key configuration.");
      }
      headers["Authorization"] = resolvedApiKey;

      // Extract and add tenant_id and keycloak_id from metadata
      try {
        const metadataObj =
          metadata && metadata !== "{}" ? JSON.parse(metadata) : {};
        if (metadataObj.tenant_id) {
          headers["x-tenant-id"] = metadataObj.tenant_id;
        }
        if (metadataObj.keycloak_id) {
          headers["x-keycloak-id"] = metadataObj.keycloak_id;
        }
      } catch (e) {
        console.warn("Failed to parse metadata for headers:", e);
      }

      const response = await fetch(`${API_BASE_URL}/kyc/verify`, {
        method: "POST",
        headers,
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error("Verification failed:", errorText);

        // Set status to REJECTED and show error
        setStatus("REJECTED");
        setError(`Verification failed: ${response.statusText}. ${errorText}`);
        return;
      }

      // Try to parse JSON response, handle empty responses
      let result = null;
      const responseText = await response.text();
      if (responseText) {
        try {
          result = JSON.parse(responseText);
          console.log("Verification result:", result);
        } catch (e) {
          console.warn("Failed to parse verification response as JSON:", e);
          console.warn("Non-JSON response received:", responseText);
        }
      }

      // Set status to VERIFIED after successful API response
      setStatus("VERIFIED");
      console.log("Verification submitted successfully");
    } catch (err) {
      console.error("Failed to submit verification:", err);
      setStatus("REJECTED");
      setError(
        err instanceof Error ? err.message : "Failed to submit verification",
      );
    } finally {
      setSubmitting(false);
    }
  };

  const finalizeLiveness = useCallback(async () => {
    setStatus("VERIFYING");

    // Stop animation loop
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
    }

    // Calculate final signals
    const avgMotion =
      motionHistoryRef.current.length > 0
        ? motionHistoryRef.current.reduce((a, b) => a + b, 0) /
          motionHistoryRef.current.length
        : 0;

    // Calculate timing variance from challenge response times
    const calculateTimingVariance = (times: number[]): number => {
      if (times.length < 2) return 0;
      const mean = times.reduce((a, b) => a + b, 0) / times.length;
      const variance =
        times.reduce((sum, time) => sum + Math.pow(time - mean, 2), 0) /
        times.length;
      return Math.min(Math.sqrt(variance) / 1000, 1); // Normalize to 0-1
    };

    // Calculate light variance from brightness history
    const calculateLightVariance = (brightness: number[]): number => {
      if (brightness.length < 2) return 0;
      const mean = brightness.reduce((a, b) => a + b, 0) / brightness.length;
      const variance =
        brightness.reduce((sum, b) => sum + Math.pow(b - mean, 2), 0) /
        brightness.length;
      return Math.min(Math.sqrt(variance) / 50, 1); // Normalize to 0-1
    };

    // Calculate average frame difference
    const avgFrameDiff =
      diffHistoryRef.current.length > 0
        ? diffHistoryRef.current.reduce((a, b) => a + b, 0) /
          diffHistoryRef.current.length
        : 0;

    const timingVar = calculateTimingVariance(
      challengeResponseTimesRef.current,
    );
    const lightVar = calculateLightVariance(brightnessHistoryRef.current);

    const signalInputs: SignalInputs = {
      motion: avgMotion,
      challengePassed: allChallengesPassedRef.current,
      timingVariance: timingVar,
      lightVariance: lightVar,
      frameDiff: avgFrameDiff,
    };

    const signals = scoreEngine(signalInputs);

    // More lenient: if enough challenges passed, be flexible on motion requirement
    const totalChallenges = totalChallengesRef.current;
    const passedCount = passedChallengesCountRef.current;
    const halfRequired = Math.ceil(totalChallenges / 2);
    const passedEnoughChallenges = passedCount >= halfRequired;

    // Pass if: challenges passed AND (has decent motion OR has any motion with good score)
    const verdict =
      (passedEnoughChallenges && avgMotion > 0.01) ||
      (passedEnoughChallenges && signals.score > 0.5)
        ? "VERIFIED"
        : "REJECTED";

    console.log("\n=== FINAL VERDICT ===");
    console.log(
      `Challenges: ${passedCount}/${totalChallenges} passed (need ${halfRequired})`,
    );
    console.log(`Passed Enough: ${passedEnoughChallenges}`);
    console.log(`Avg Motion: ${avgMotion.toFixed(5)}`);
    console.log(`Signal Score: ${signals.score.toFixed(3)}`);
    console.log(`Verdict: ${verdict}`);
    console.log(`Signals:`, signals);
    console.log("=====================\n");
    const livenessProof = buildProof(signals, verdict);

    // Generate hash for the proof
    const proofHash = await hashProof(livenessProof);
    const proofWithHash = {
      ...livenessProof,
      hash: proofHash,
    };

    setProof(proofWithHash);
    // Don't set status to VERIFIED yet - wait for API response
    // setStatus(verdict === "VERIFIED" ? "VERIFIED" : "REJECTED");

    // Log proof report
    console.log(generateProofReport(livenessProof));

    // Submit verification - status will be set after API responds
    if (verdict === "VERIFIED") {
      await submitVerification(proofWithHash);
    } else {
      setStatus("REJECTED");
    }
  }, []);

  // Frame processing loop
  const processFrame = useCallback(() => {
    if (!videoRef.current || !canvasRef.current || status !== "CHALLENGE") {
      return;
    }

    const video = videoRef.current;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");

    if (!ctx || video.readyState !== video.HAVE_ENOUGH_DATA) {
      animationFrameRef.current = requestAnimationFrame(processFrame);
      return;
    }

    // Capture current frame
    const currentFrameData = captureFrame(video, canvas, ctx);
    frameBufferRef.current = addToBuffer(
      frameBufferRef.current,
      currentFrameData,
      10,
    );

    if (prevFrameRef.current) {
      // Calculate motion
      const rawMotion = motionScore(
        prevFrameRef.current,
        currentFrameData.imageData,
      );

      // Calibrate noise floor during first 30 frames (1 second at 30fps)
      if (noiseCalibrationRef.current.length < 30) {
        noiseCalibrationRef.current.push(rawMotion);
        if (noiseCalibrationRef.current.length === 30) {
          // Use minimum value as noise floor - most conservative approach
          const sorted = [...noiseCalibrationRef.current].sort((a, b) => a - b);
          const minValue = sorted[0];
          noiseFloorRef.current = minValue * 0.5; // Only 50% of minimum to preserve motion
          console.log(
            `Camera noise floor calibrated: ${noiseFloorRef.current.toFixed(5)}`,
          );
          console.log(
            `   (Min: ${minValue.toFixed(5)}, Range: ${sorted[0].toFixed(5)} - ${sorted[sorted.length - 1].toFixed(5)})`,
          );
        }
      }

      // Filter motion: subtract noise floor, clamp to 0, then amplify small motions
      let motion = Math.max(0, rawMotion - noiseFloorRef.current);
      // Amplify small motions to make them more detectable (1.5x for motions < 0.01)
      if (motion > 0 && motion < 0.01) {
        motion = motion * 1.5;
      }

      console.log(
        `Motion: raw=${rawMotion.toFixed(5)}, noise=${noiseFloorRef.current.toFixed(5)}, filtered=${motion.toFixed(5)}`,
      );

      // Adaptive noise floor: if we see very low motion consistently, lower the floor
      if (noiseCalibrationRef.current.length >= 30) {
        const recentRaw = motionHistoryRef.current.slice(-10).map((m, i) => {
          // Reconstruct raw motion by adding back the noise floor
          console.log(
            `Recent motion ${i}: filtered=${m.toFixed(5)}, raw=${(m + noiseFloorRef.current).toFixed(5)}`,
          );
          return m + noiseFloorRef.current;
        });
        if (recentRaw.length >= 10) {
          const avgRecent =
            recentRaw.reduce((a, b) => a + b, 0) / recentRaw.length;
          // If average raw motion is very low, assume it's camera noise and adjust
          if (avgRecent < noiseFloorRef.current * 0.2 && avgRecent > 0) {
            noiseFloorRef.current = Math.max(0.0002, avgRecent * 0.8);
          }
        }
      }

      motionHistoryRef.current.push(motion);
      if (motionHistoryRef.current.length > 60) {
        motionHistoryRef.current.shift();
      }

      // Calculate frame difference
      const diff = frameDiff(prevFrameRef.current, currentFrameData.imageData);
      diffHistoryRef.current.push(diff);
      if (diffHistoryRef.current.length > 60) {
        diffHistoryRef.current.shift();
      }

      // Calculate brightness
      const brightness = getAverageBrightness(currentFrameData.imageData);
      brightnessHistoryRef.current.push(brightness);
      if (brightnessHistoryRef.current.length > 60) {
        brightnessHistoryRef.current.shift();
      }

      // Check for challenge completion or timeout
      const elapsed = Date.now() - challengeStartRef.current;
      const maxChallengeTime = 10000; // 10 seconds max per challenge

      // Calculate average motion for debugging
      const avgMotion =
        motionHistoryRef.current.length > 0
          ? motionHistoryRef.current.reduce((a, b) => a + b, 0) /
            motionHistoryRef.current.length
          : 0;

      // Update debug display
      setDebugMotion(motion);
      setDebugAvgMotion(avgMotion);

      // Calculate progress across all challenges (0-100%)
      const challengeProgress = Math.min(
        (elapsed / maxChallengeTime) * 100,
        100,
      );
      const baseProgress = (currentChallengeIndex / challenges.length) * 100;
      const currentProgress =
        baseProgress + challengeProgress / challenges.length;
      setProgress(Math.min(currentProgress, 100));

      // Verify if challenge was actually completed
      const challengeCompleted =
  challenge &&
  verifyChallengeResponse(
    challenge,
    motion,
    motionHistoryRef.current,
    prevFrameRef.current,
    currentFrameData.imageData
  );

      // Console log for debugging every second
      if (Math.floor(elapsed / 1000) !== Math.floor((elapsed - 16) / 1000)) {
        const recentMotionSample = motionHistoryRef.current.slice(-15);
        const recentAvg =
          recentMotionSample.length > 0
            ? recentMotionSample.reduce((a, b) => a + b, 0) /
              recentMotionSample.length
            : 0;
        const recentMax =
          recentMotionSample.length > 0 ? Math.max(...recentMotionSample) : 0;

        console.log(
          `\n=== Challenge: ${challenge} (${(elapsed / 1000).toFixed(1)}s) ===`,
        );
        console.log(`Noise Floor: ${noiseFloorRef.current.toFixed(5)}`);
        console.log(
          `Current (filtered): ${motion.toFixed(5)}, Avg: ${avgMotion.toFixed(5)}`,
        );
        console.log(
          `Recent: avg=${recentAvg.toFixed(5)}, max=${recentMax.toFixed(5)}`,
        );
        console.log(`Would Pass: ${challengeCompleted}`);
        console.log(`====================================\n`);
      }

      if (challengeCompleted && !challengeDetectedRef.current) {
        // Challenge successfully completed
        challengeDetectedRef.current = true;
        setChallengeSuccess(true);
        passedChallengesCountRef.current += 1;
        console.log(
          `✓ Challenge "${challenge}" PASSED! (${passedChallengesCountRef.current}/${totalChallengesRef.current})`,
        );
        const responseTime = elapsed;
        challengeResponseTimesRef.current.push(responseTime);

        // Wait a moment before moving to next challenge
        setTimeout(() => {
          setChallengeSuccess(false);
          if (currentChallengeIndex < challenges.length - 1) {
            // Move to next challenge
            const nextIndex = currentChallengeIndex + 1;
            setCurrentChallengeIndex(nextIndex);
            setChallenge(challenges[nextIndex]);
            challengeStartRef.current = Date.now();
            challengeDetectedRef.current = false;
          } else {
            // All challenges attempted - check if enough passed
            const halfRequired = Math.ceil(totalChallengesRef.current / 2);
            allChallengesPassedRef.current =
              passedChallengesCountRef.current >= halfRequired;
            console.log(
              `Challenge completion: ${passedChallengesCountRef.current}/${totalChallengesRef.current} (need ${halfRequired})`,
            );
            finalizeLiveness();
          }
        }, 800);
      } else if (elapsed > maxChallengeTime) {
        // Challenge timeout - mark as failed
        challengeResponseTimesRef.current.push(maxChallengeTime);

        // Wait before moving to next challenge
        setTimeout(() => {
          // Move to next challenge or finalize
          if (currentChallengeIndex < challenges.length - 1) {
            const nextIndex = currentChallengeIndex + 1;
            setCurrentChallengeIndex(nextIndex);
            setChallenge(challenges[nextIndex]);
            challengeStartRef.current = Date.now();
            challengeDetectedRef.current = false;
          } else {
            // All challenges attempted - check if enough passed
            const halfRequired = Math.ceil(totalChallengesRef.current / 2);
            allChallengesPassedRef.current =
              passedChallengesCountRef.current >= halfRequired;
            console.log(
              `Challenge completion (timeout): ${passedChallengesCountRef.current}/${totalChallengesRef.current} (need ${halfRequired})`,
            );
            finalizeLiveness();
          }
        }, 2000);
        return;
      }
    }

    prevFrameRef.current = currentFrameData.imageData;
    animationFrameRef.current = requestAnimationFrame(processFrame);
  }, [status, challenge, challenges, currentChallengeIndex, finalizeLiveness]);

  const startDocumentCamera = async () => {
    try {
      if (!documentVideoRef.current) return;

      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment" },
        audio: false,
      });

      documentVideoRef.current.srcObject = stream;
      documentStreamRef.current = stream;

      // Ensure video starts playing
      await documentVideoRef.current.play().catch((err) => {
        console.error("Failed to play video:", err);
      });
    } catch (err) {
      console.error("Failed to start document camera:", err);
    }
  };

  const captureDocument = () => {
    if (!documentVideoRef.current || !documentCanvasRef.current) {
      return null;
    }

    const video = documentVideoRef.current;
    const canvas = documentCanvasRef.current;

    if (video.videoWidth === 0 || video.videoHeight === 0) {
      return null;
    }

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    const ctx = canvas.getContext("2d");
    if (!ctx) {
      return null;
    }

    ctx.drawImage(video, 0, 0);
    const imageData = canvas.toDataURL("image/jpeg", 0.8);
    return imageData;
  };

  const stopDocumentCamera = () => {
    if (documentStreamRef.current) {
      documentStreamRef.current.getTracks().forEach((track) => track.stop());
      documentStreamRef.current = null;
    }
  };

  const startLiveness = async () => {
    try {
      setStatus("INITIALIZING");
      setError(null);

      // Reset all counters
      passedChallengesCountRef.current = 0;
      allChallengesPassedRef.current = false;
      challengeResponseTimesRef.current = [];

      // Reset noise calibration
      noiseFloorRef.current = 0;
      noiseCalibrationRef.current = [];

      if (!videoRef.current) {
        throw new Error("Video element not available");
      }

      // Initialize camera
      const stream = await initCamera(videoRef.current);
      streamRef.current = stream;

      setStatus("READY");

      // Countdown before challenge
      let count = 3;
      setCountdown(count);
      const countdownInterval = setInterval(() => {
        count--;
        setCountdown(count);
        if (count === 0) {
          clearInterval(countdownInterval);

          // Generate 4 challenges
          const newChallenges = [
            generateChallenge(),
            generateChallenge(),
            generateChallenge(),
            generateChallenge(),
          ];
          setChallenges(newChallenges);
          totalChallengesRef.current = newChallenges.length;
          setCurrentChallengeIndex(0);
          setChallenge(newChallenges[0]);
          setStatus("CHALLENGE");
          challengeStartRef.current = Date.now();
          challengeDetectedRef.current = false;
          setProgress(0);

          // Reset buffers
          motionHistoryRef.current = [];
          diffHistoryRef.current = [];
          brightnessHistoryRef.current = [];
          frameBufferRef.current = [];
          prevFrameRef.current = null;
        }
      }, 1000);
    } catch (err) {
      setStatus("IDLE");
      setError(
        err instanceof Error ? err.message : "Failed to start liveness check",
      );
    }
  };

  const reset = () => {
    if (streamRef.current) {
      stopCamera(streamRef.current);
      streamRef.current = null;
    }

    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
    }

    setStatus("IDLE");
    setChallenge(null);
    setChallenges([]);
    setCurrentChallengeIndex(0);
    setProgress(0);
    setProof(null);
    setError(null);
    setCountdown(3);
    setDocumentStep("idle");
    setFrontDocument(null);
    setBackDocument(null);
  };

  // Commented out - downloadProof is not currently used
  // const downloadProof = () => {
  //   if (!proof) return;

  //   const report = generateProofReport(proof);
  //   const blob = new Blob([report], { type: "text/plain" });
  //   const url = URL.createObjectURL(blob);
  //   const a = document.createElement("a");
  //   a.href = url;
  //   a.download = `liveness-proof-${proof.sessionId}.txt`;
  //   document.body.appendChild(a);
  //   a.click();
  //   document.body.removeChild(a);
  //   URL.revokeObjectURL(url);
  // };

  // Start frame processing when in challenge state
  useEffect(() => {
    if (status === "CHALLENGE") {
      animationFrameRef.current = requestAnimationFrame(processFrame);
    }

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [status, processFrame]);

  // Start document camera when entering document capture screens
  useEffect(() => {
    if (documentStep === "front" && !frontDocument) {
      startDocumentCamera();
    } else if (documentStep === "back" && !backDocument) {
      startDocumentCamera();
    }

    return () => {
      if (documentStep !== "front" && documentStep !== "back") {
        stopDocumentCamera();
      }
    };
  }, [documentStep, frontDocument, backDocument]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (streamRef.current) {
        stopCamera(streamRef.current);
      }
      if (documentStreamRef.current) {
        stopDocumentCamera();
      }
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, []);

  // Check for valid verification_id on mount
  useEffect(() => {
    if (!verification_id || verification_id.trim() === "") {
      setError(
        "Invalid verification URL. Please use a valid verification link from your application.",
      );
    }
  }, [verification_id]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-100 to-slate-200 flex items-center justify-center p-4">
      <canvas ref={canvasRef} className="hidden" />
      <canvas ref={documentCanvasRef} className="hidden" />

      <div className="w-full max-w-md bg-white rounded-[32px] shadow-2xl overflow-hidden relative">
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          className={
            status === "READY" || status === "CHALLENGE"
              ? "absolute inset-0 w-full h-full object-cover z-10"
              : "hidden"
          }
        />

        {status === "IDLE" && documentStep === "idle" && (
          <div className="p-8 flex flex-col items-center">
            <h1 className="text-2xl font-bold text-slate-800 mb-2 text-center">
              54agent Identity Verification
            </h1>
            <p className="text-sm text-slate-500 mb-6 text-center">
              We need to verify your identity to continue
            </p>

            <div className="w-full bg-blue-50 rounded-2xl p-6 mb-8">
              <h3 className="text-sm font-semibold text-blue-900 mb-3">
                Before you start:
              </h3>
              <ul className="space-y-2 text-xs text-blue-800">
                <li className="flex items-start">
                  <svg
                    className="w-4 h-4 mr-2 mt-0.5 flex-shrink-0"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path
                      fillRule="evenodd"
                      d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                      clipRule="evenodd"
                    />
                  </svg>
                  <span>Have your ID card ready</span>
                </li>
                <li className="flex items-start">
                  <svg
                    className="w-4 h-4 mr-2 mt-0.5 flex-shrink-0"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path
                      fillRule="evenodd"
                      d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                      clipRule="evenodd"
                    />
                  </svg>
                  <span>Move to a well-lit area</span>
                </li>
                <li className="flex items-start">
                  <svg
                    className="w-4 h-4 mr-2 mt-0.5 flex-shrink-0"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path
                      fillRule="evenodd"
                      d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                      clipRule="evenodd"
                    />
                  </svg>
                  <span>Remove glasses and face coverings</span>
                </li>
                <li className="flex items-start">
                  <svg
                    className="w-4 h-4 mr-2 mt-0.5 flex-shrink-0"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path
                      fillRule="evenodd"
                      d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                      clipRule="evenodd"
                    />
                  </svg>
                  <span>Follow on-screen instructions</span>
                </li>
              </ul>
            </div>

            <button
              onClick={() => setDocumentStep("front")}
              disabled={!verification_id || verification_id.trim() === ""}
              className="w-full bg-slate-900 hover:bg-slate-800 disabled:bg-slate-400 disabled:cursor-not-allowed text-white font-semibold py-4 px-6 rounded-2xl transition-all transform hover:scale-[1.02] active:scale-[0.98] disabled:scale-100 shadow-lg"
            >
              Start Verification
            </button>

            <p className="text-xs text-slate-400 mt-6 text-center">
              Secure verification powered by 54agent
            </p>
          </div>
        )}

        {documentStep === "front" && (
          <div className="flex flex-col min-h-[600px]">
            <div className="p-8 pb-4">
              <div className="w-full flex items-center mb-6">
                <button
                  onClick={() => {
                    stopDocumentCamera();
                    setDocumentStep("idle");
                  }}
                  className="p-2 hover:bg-slate-100 rounded-lg"
                >
                  <svg
                    className="w-6 h-6 text-slate-600"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M15 19l-7-7 7-7"
                    />
                  </svg>
                </button>
                <h1 className="flex-1 text-xl font-bold text-slate-800 text-center mr-8">
                  Identity Document
                </h1>
              </div>
              <p className="text-sm text-slate-500 mb-4 text-center">
                Take a photo of the front of your ID card
              </p>
            </div>

            <div className="flex-1 relative bg-slate-900">
              {!frontDocument ? (
                <>
                  <video
                    ref={documentVideoRef}
                    autoPlay
                    playsInline
                    className="absolute inset-0 w-full h-full object-cover"
                  />
                  <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                    <div className="border-4 border-white rounded-3xl w-[320px] h-[200px] shadow-2xl">
                      <div className="absolute -top-12 left-1/2 transform -translate-x-1/2 bg-white px-4 py-2 rounded-xl">
                        <p className="text-sm text-slate-800 font-medium">
                          Position card in frame
                        </p>
                      </div>
                    </div>
                  </div>
                </>
              ) : (
                <img
                  src={frontDocument}
                  alt="Front of ID"
                  className="w-full h-full object-cover"
                />
              )}
            </div>

            <div className="p-8 pt-4">
              {!frontDocument ? (
                <button
                  onClick={() => {
                    const image = captureDocument();
                    if (image) {
                      setFrontDocument(image);
                      stopDocumentCamera();
                    }
                  }}
                  className="w-full bg-blue-500 hover:bg-blue-600 text-white font-semibold py-4 px-6 rounded-2xl transition-colors"
                >
                  Take Photo
                </button>
              ) : (
                <div className="space-y-3">
                  <button
                    onClick={() => {
                      setFrontDocument(null);
                    }}
                    className="w-full bg-blue-500 hover:bg-blue-600 text-white font-semibold py-4 px-6 rounded-2xl transition-colors"
                  >
                    Retake Photo
                  </button>
                  <button
                    onClick={() => setDocumentStep("back")}
                    className="w-full bg-slate-900 hover:bg-slate-800 text-white font-semibold py-4 px-6 rounded-2xl transition-colors"
                  >
                    Continue
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

        {documentStep === "back" && (
          <div className="flex flex-col min-h-[600px]">
            <div className="p-8 pb-4">
              <div className="w-full flex items-center mb-6">
                <button
                  onClick={() => {
                    stopDocumentCamera();
                    setDocumentStep("front");
                  }}
                  className="p-2 hover:bg-slate-100 rounded-lg"
                >
                  <svg
                    className="w-6 h-6 text-slate-600"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M15 19l-7-7 7-7"
                    />
                  </svg>
                </button>
                <h1 className="flex-1 text-xl font-bold text-slate-800 text-center mr-8">
                  Identity Document
                </h1>
              </div>
              <p className="text-sm text-slate-500 mb-14 text-center">
                Take a photo of the back of your ID card
              </p>
            </div>

            <div className="flex-1 relative bg-slate-900">
              {!backDocument ? (
                <>
                  <video
                    ref={documentVideoRef}
                    autoPlay
                    playsInline
                    className="absolute inset-0 w-full h-full object-cover"
                  />
                  <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                    <div className="border-4 border-white rounded-3xl w-[320px] h-[200px] shadow-2xl">
                      <div className="absolute -top-12 left-1/2 transform -translate-x-1/2 bg-white px-4 py-2 rounded-xl">
                        <p className="text-sm text-slate-800 font-medium">
                          Position card in frame
                        </p>
                      </div>
                    </div>
                  </div>
                </>
              ) : (
                <img
                  src={backDocument}
                  alt="Back of ID"
                  className="w-full h-full object-cover"
                />
              )}
            </div>

            <div className="p-8 pt-4">
              {!backDocument ? (
                <button
                  onClick={() => {
                    const image = captureDocument();
                    if (image) {
                      setBackDocument(image);
                      stopDocumentCamera();
                    }
                  }}
                  className="w-full bg-blue-500 hover:bg-blue-600 text-white font-semibold py-4 px-6 rounded-2xl transition-colors"
                >
                  Take Photo
                </button>
              ) : (
                <div className="space-y-3">
                  <button
                    onClick={() => {
                      setBackDocument(null);
                    }}
                    className="w-full bg-blue-500 hover:bg-blue-600 text-white font-semibold py-4 px-6 rounded-2xl transition-colors"
                  >
                    Retake Photo
                  </button>
                  <button
                    onClick={() => {
                      setDocumentStep("complete");
                      startLiveness();
                    }}
                    className="w-full bg-slate-900 hover:bg-slate-800 text-white font-semibold py-4 px-6 rounded-2xl transition-colors"
                  >
                    Continue to Face Verification
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

        {status === "INITIALIZING" && (
          <div className="p-8 flex flex-col items-center justify-center min-h-[600px]">
            <div className="relative">
              <div className="w-16 h-16 border-4 border-blue-200 border-t-blue-500 rounded-full animate-spin"></div>
            </div>
            <p className="text-slate-700 font-medium mt-6">
              Initializing camera...
            </p>
          </div>
        )}

        {status === "READY" && countdown > 0 && (
          <div className="relative min-h-[600px] bg-slate-900 overflow-hidden z-0">
            <div className="absolute inset-0 bg-black/50 backdrop-blur-sm flex flex-col items-center justify-center z-20">
              <div className="text-white text-8xl font-bold mb-4 animate-pulse">
                {countdown}
              </div>
              <p className="text-white text-lg">Get ready...</p>
            </div>
          </div>
        )}

        {status === "CHALLENGE" && (
          <div className="relative min-h-[600px] overflow-hidden z-20">
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-30">
              <div className="relative">
                <div
                  className={`w-64 h-80 border-4 rounded-[50%] shadow-2xl transition-colors duration-300 ${
                    challengeSuccess ? "border-green-400" : "border-white"
                  }`}
                ></div>
                <div
                  className={`absolute -top-8 left-1/2 transform -translate-x-1/2 px-6 py-3 rounded-2xl shadow-lg transition-colors duration-300 ${
                    challengeSuccess ? "bg-green-500" : "bg-white"
                  }`}
                >
                  <p
                    className={`font-semibold text-center whitespace-nowrap transition-colors duration-300 ${
                      challengeSuccess ? "text-white" : "text-slate-800"
                    }`}
                  >
                    {challengeSuccess
                      ? "✓ Success!"
                      : challenge && getChallengeInstruction(challenge)}
                  </p>
                </div>
                <div className="absolute -bottom-12 left-1/2 transform -translate-x-1/2 bg-white/90 px-4 py-2 rounded-xl shadow-lg">
                  <p className="text-xs text-slate-600 font-medium">
                    Task {currentChallengeIndex + 1} of {challenges.length}
                  </p>
                </div>
              </div>
            </div>

            {/* Debug Motion Display */}
            {/* <div className="absolute top-4 left-4 bg-black/70 text-white px-3 py-2 rounded-lg font-mono text-xs z-40">
              <div>Motion: {debugMotion.toFixed(4)}</div>
              <div>Avg: {debugAvgMotion.toFixed(4)}</div>
              <div>Noise: {noiseFloorRef.current.toFixed(4)}</div>
              <div
                className={`mt-1 ${
                  debugMotion > 0.015
                    ? "text-green-400"
                    : debugMotion > 0.008
                      ? "text-yellow-400"
                      : "text-red-400"
                }`}
              >
                {debugMotion > 0.015
                  ? "✓ Good"
                  : debugMotion > 0.008
                    ? "~ OK"
                    : "✗ Too Low"}
              </div>
              <div className="text-xs text-gray-400 mt-1">Need: ~0.012</div>
            </div> */}

            <div className="absolute bottom-0 left-0 right-0 z-40">
              <div className="bg-gray-800/50 w-full h-3 overflow-hidden">
                <div
                  className="bg-gradient-to-r from-blue-500 to-green-400 h-full transition-all duration-300"
                  style={{ width: `${progress}%` }}
                ></div>
              </div>
            </div>
          </div>
        )}

        {status === "VERIFYING" && (
          <div className="p-8 flex flex-col items-center justify-center min-h-[600px]">
            <div className="relative">
              <div className="w-16 h-16 border-4 border-blue-200 border-t-blue-500 rounded-full animate-spin"></div>
            </div>
            <p className="text-slate-700 font-medium mt-6">
              Verifying your identity...
            </p>
            <p className="text-slate-500 text-sm mt-2">
              Please wait while we process your verification
            </p>
          </div>
        )}

        {status === "VERIFIED" && proof && (
          <div className="p-8">
            <div className="flex flex-col items-center mb-8">
              <div className="w-20 h-20 bg-green-500 rounded-full flex items-center justify-center mb-4">
                <svg
                  className="w-12 h-12 text-white"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={3}
                    d="M5 13l4 4L19 7"
                  />
                </svg>
              </div>
              <h2 className="text-3xl font-bold text-slate-800 mb-2">
                Verified!
              </h2>
              <p className="text-slate-600">Your identity has been confirmed</p>
            </div>

            <div className="bg-slate-50 rounded-2xl p-6 mb-6">
              <div className="space-y-4">
                {/* <div className="flex justify-between items-center">
                  <span className="text-slate-600 font-medium">
                    Confidence Score
                  </span>
                  <span className="text-2xl font-bold text-green-500">
                    {(proof.confidence * 100).toFixed(1)}%
                  </span>
                </div> */}

                <div className="mt-4 p-4 bg-blue-50 rounded-lg border border-blue-200">
                  <p className="text-sm text-blue-900 font-medium mb-1">
                    ✓ Verification Complete
                  </p>
                  <p className="text-xs text-blue-700">
                    You can now close this page and return to the application.
                  </p>
                </div>
              </div>
            </div>

            {/* <div className="flex gap-3">
              <button
                onClick={downloadProof}
                className="flex-1 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold py-3 px-6 rounded-xl transition-colors"
              >
                Download Proof
              </button>
            </div> */}
          </div>
        )}

        {status === "REJECTED" && proof && (
          <div className="p-8">
            <div className="flex flex-col items-center mb-8">
              <div className="w-20 h-20 bg-red-500 rounded-full flex items-center justify-center mb-4">
                <svg
                  className="w-12 h-12 text-white"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={3}
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </div>
              <h2 className="text-3xl font-bold text-slate-800 mb-2">
                Verification Failed
              </h2>
              <p className="text-slate-600 text-center">
                Please try again with better lighting and follow instructions
                carefully
              </p>
            </div>

            <button
              onClick={reset}
              className="w-full bg-blue-500 hover:bg-blue-600 text-white font-semibold py-4 px-6 rounded-xl transition-colors"
            >
              Try Again
            </button>
          </div>
        )}

        {error && (
          <div className="p-4 bg-red-50 border-l-4 border-red-500 mx-8 my-4 rounded">
            <div className="flex">
              <div className="flex-shrink-0">
                <svg
                  className="h-5 w-5 text-red-400"
                  viewBox="0 0 20 20"
                  fill="currentColor"
                >
                  <path
                    fillRule="evenodd"
                    d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                    clipRule="evenodd"
                  />
                </svg>
              </div>
              <div className="ml-3">
                <p className="text-sm text-red-700">{error}</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
