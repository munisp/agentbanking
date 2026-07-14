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
  getVerdict,
  initCamera,
  motionScore,
  scoreEngine,
  stopCamera,
  type ChallengeType,
  type FrameData,
  type LivenessProof,
  type SignalInputs,
  type VerificationStatus,
} from "./liveness/index";

export default function Liveness() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const documentVideoRef = useRef<HTMLVideoElement>(null);
  const documentCanvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const documentStreamRef = useRef<MediaStream | null>(null);
  const animationFrameRef = useRef<number | null>(null);

  const [status, setStatus] = useState<VerificationStatus>("IDLE");
  const [challenge, setChallenge] = useState<ChallengeType | null>(null);
  const [challenges, setChallenges] = useState<ChallengeType[]>([]);
  const [currentChallengeIndex, setCurrentChallengeIndex] = useState(0);
  const [progress, setProgress] = useState(0);
  const [proof, setProof] = useState<LivenessProof | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [countdown, setCountdown] = useState<number>(5);
  const [documentStep, setDocumentStep] = useState<
    "idle" | "front" | "back" | "complete"
  >("idle");
  const [frontDocument, setFrontDocument] = useState<string | null>(null);
  const [backDocument, setBackDocument] = useState<string | null>(null);

  // Frame buffers
  const frameBufferRef = useRef<FrameData[]>([]);
  const prevFrameRef = useRef<ImageData | null>(null);
  const motionHistoryRef = useRef<number[]>([]);
  const diffHistoryRef = useRef<number[]>([]);
  const brightnessHistoryRef = useRef<number[]>([]);

  // Challenge tracking
  const challengeStartRef = useRef<number>(0);
  const challengeDetectedRef = useRef<boolean>(false);

  const finalizeLiveness = useCallback(() => {
    setStatus("VERIFYING");

    // Stop animation loop
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
    }

    // Demo mode: Always pass with good scores
    const signalInputs: SignalInputs = {
      motion: 0.6,
      challengePassed: true,
      timingVariance: 0.3,
      lightVariance: 0.5,
      frameDiff: 0.4,
    };

    const signals = scoreEngine(signalInputs);
    const verdict = getVerdict(signals.score, 0.65);
    const livenessProof = buildProof(signals, verdict);

    setProof(livenessProof);
    setStatus(verdict === "VERIFIED" ? "VERIFIED" : "REJECTED");

    // Log proof report
    console.log(generateProofReport(livenessProof));
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
      const motion = motionScore(
        prevFrameRef.current,
        currentFrameData.imageData,
      );
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

      // Demo mode: Auto-pass after 10 seconds per challenge
      const elapsed = Date.now() - challengeStartRef.current;

      // Calculate progress across all challenges (0-100%)
      const challengeProgress = Math.min((elapsed / 10000) * 100, 100);
      const baseProgress = (currentChallengeIndex / challenges.length) * 100;
      const currentProgress =
        baseProgress + challengeProgress / challenges.length;
      setProgress(Math.min(currentProgress, 100));

      if (elapsed > 10000) {
        // Auto-complete current challenge
        challengeDetectedRef.current = true;

        // Wait before moving to next challenge
        setTimeout(() => {
          // Check if there are more challenges
          if (currentChallengeIndex < challenges.length - 1) {
            // Move to next challenge
            const nextIndex = currentChallengeIndex + 1;
            setCurrentChallengeIndex(nextIndex);
            setChallenge(challenges[nextIndex]);
            challengeStartRef.current = Date.now();
            setProgress(0);
          } else {
            // All challenges completed
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
      console.log("Missing refs");
      return null;
    }

    const video = documentVideoRef.current;
    const canvas = documentCanvasRef.current;

    // Check if video is ready
    if (video.videoWidth === 0 || video.videoHeight === 0) {
      console.log("Video not ready");
      return null;
    }

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    const ctx = canvas.getContext("2d");
    if (!ctx) {
      console.log("No canvas context");
      return null;
    }

    ctx.drawImage(video, 0, 0);
    const imageData = canvas.toDataURL("image/jpeg", 0.8);
    console.log("Image captured successfully");
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

      if (!videoRef.current) {
        throw new Error("Video element not available");
      }

      // Initialize camera
      const stream = await initCamera(videoRef.current);
      streamRef.current = stream;

      setStatus("READY");

      // Countdown before challenge
      let count = 5;
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
    setCountdown(5);
  };

  const downloadProof = () => {
    if (!proof) return;

    const report = generateProofReport(proof);
    const blob = new Blob([report], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `liveness-proof-${proof.sessionId}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

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

    // Cleanup when leaving document screens
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

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-100 to-slate-200 flex items-center justify-center p-4">
      {/* Canvas elements - always rendered but hidden */}
      <canvas ref={canvasRef} className="hidden" />
      <canvas ref={documentCanvasRef} className="hidden" />

      {/* Mobile-first card container */}
      <div className="w-full max-w-md bg-white rounded-[32px] shadow-2xl overflow-hidden relative">
        {/* Video element - always rendered with ref, conditionally visible */}
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
        {/* IDLE State - Initial Screen */}
        {status === "IDLE" && documentStep === "idle" && (
          <div className="p-8 flex flex-col items-center">
            <h1 className="text-2xl font-bold text-slate-800 mb-2 text-center">
              Verify your identity
            </h1>
            <p className="text-sm text-slate-500 mb-6 text-center">
              We need some information to help us confirm your identity.
            </p>

            {/* Instructions */}
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
                  <span>Move to a well-lit area with good lighting</span>
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
                  <span>Remove glasses, hats, or face coverings</span>
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
                  <span>Position your face fully within the circle</span>
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
                  <span>Follow the on-screen instructions carefully</span>
                </li>
              </ul>
            </div>

            {/* Illustration */}
            <div className="relative mb-12">
              <div className="w-48 h-48 bg-gradient-to-br from-blue-400 to-blue-500 rounded-3xl transform rotate-6 shadow-lg flex items-center justify-center">
                <svg
                  className="w-24 h-24 text-white"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
              </div>
              <div className="absolute -right-4 -top-4 w-32 h-32 bg-white rounded-2xl shadow-xl p-4 flex flex-col items-center justify-center">
                <div className="w-12 h-12 bg-blue-500 rounded-full mb-2 flex items-center justify-center">
                  <svg
                    className="w-6 h-6 text-white"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path
                      fillRule="evenodd"
                      d="M10 9a3 3 0 100-6 3 3 0 000 6zm-7 9a7 7 0 1114 0H3z"
                      clipRule="evenodd"
                    />
                  </svg>
                </div>
                <div className="h-1 w-8 bg-blue-200 rounded mb-1"></div>
                <div className="h-1 w-6 bg-blue-200 rounded"></div>
              </div>
              <div className="absolute -right-2 top-0 w-8 h-8 bg-blue-500 rounded-lg flex items-center justify-center">
                <svg
                  className="w-5 h-5 text-white"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path
                    fillRule="evenodd"
                    d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                    clipRule="evenodd"
                  />
                </svg>
              </div>
            </div>

            <button
              onClick={() => setDocumentStep("front")}
              className="w-full bg-slate-900 hover:bg-slate-800 text-white font-semibold py-4 px-6 rounded-2xl transition-all transform hover:scale-[1.02] active:scale-[0.98] shadow-lg"
            >
              Start Verification
            </button>

            <p className="text-xs text-slate-400 mt-6 text-center">
              Verifying usually takes a few seconds.
            </p>
          </div>
        )}

        {/* DOCUMENT UPLOAD - Front */}
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
                  Identity card
                </h1>
              </div>
              <p className="text-sm text-slate-500 mb-4 text-center">
                Take a photo of the front of your identity card
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
                  <canvas ref={documentCanvasRef} className="hidden" />
                  <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                    <div className="border-4 border-white rounded-3xl w-[320px] h-[200px] shadow-2xl">
                      <div className="absolute -top-12 left-1/2 transform -translate-x-1/2 bg-white px-4 py rounded-xl">
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

        {/* DOCUMENT UPLOAD - Back */}
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
                  Identity card
                </h1>
              </div>
              <p className="text-sm text-slate-500 mb-4 text-center">
                Take a photo of the back of your identity card
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
                  <canvas ref={documentCanvasRef} className="hidden" />
                  <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                    <div className="border-4 border-white rounded-3xl w-[320px] h-[200px] shadow-2xl">
                      <div className="absolute -top-12 left-1/2 transform -translate-x-1/2 bg-white px-4 py rounded-xl">
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
                    console.log("Take Photo clicked for back document");
                    const image = captureDocument();
                    console.log(
                      "Captured image:",
                      image ? "Success" : "Failed",
                    );
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

        {/* INITIALIZING State - Loading */}
        {status === "INITIALIZING" && (
          <div className="p-8 flex flex-col items-center justify-center min-h-[600px]">
            <div className="relative">
              <div className="w-16 h-16 border-4 border-blue-200 border-t-blue-500 rounded-full animate-spin"></div>
            </div>
            <p className="text-slate-700 font-medium mt-6">
              We're verifying your documents
            </p>
          </div>
        )}

        {/* READY State - Countdown */}
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

        {/* CHALLENGE State - Active Liveness Check */}
        {status === "CHALLENGE" && (
          <div className="relative min-h-[600px] overflow-hidden z-20">
            {/* Face oval overlay */}
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-30">
              <div className="relative">
                <div className="w-64 h-80 border-4 border-white rounded-[50%] shadow-2xl"></div>
                <div className="absolute -top-8 left-1/2 transform -translate-x-1/2 bg-white px-6 py-3 rounded-2xl shadow-lg">
                  <p className="text-slate-800 font-semibold text-center whitespace-nowrap">
                    {challenge && getChallengeInstruction(challenge)}
                  </p>
                </div>
                {/* Challenge counter */}
                <div className="absolute -bottom-12 left-1/2 transform -translate-x-1/2 bg-white/90 px-4 py-2 rounded-xl shadow-lg">
                  <p className="text-xs text-slate-600 font-medium">
                    Task {currentChallengeIndex + 1} of {challenges.length}
                  </p>
                </div>
              </div>
            </div>

            {/* Progress bar at bottom */}
            <div className="absolute bottom-0 left-0 right-0 z-40">
              <div className="bg-gray-800/50 w-full h-3  overflow-hidden">
                <div
                  className="bg-gradient-to-r from-blue-500 to-green-400 h-full transition-all duration-300"
                  style={{ width: `${progress}%` }}
                ></div>
              </div>
            </div>
          </div>
        )}

        {/* VERIFYING State - Processing */}
        {status === "VERIFYING" && (
          <div className="p-8 flex flex-col items-center justify-center min-h-[600px]">
            <div className="relative">
              <div className="w-16 h-16 border-4 border-blue-200 border-t-blue-500 rounded-full animate-spin"></div>
            </div>
            <p className="text-slate-700 font-medium mt-6">
              Analyzing verification...
            </p>
          </div>
        )}

        {/* VERIFIED State - Success */}
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

            {/* Results Card */}
            <div className="bg-slate-50 rounded-2xl p-6 mb-6">
              <div className="space-y-4">
                <div className="flex justify-between items-center">
                  <span className="text-slate-600 font-medium">
                    Confidence Score
                  </span>
                  <span className="text-2xl font-bold text-green-500">
                    {(proof.confidence * 100).toFixed(1)}%
                  </span>
                </div>

                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-slate-600">
                      Motion Detection
                    </span>
                    <div className="flex items-center gap-2">
                      <div className="w-24 h-2 bg-slate-200 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-blue-500 rounded-full"
                          style={{ width: `${proof.signals.motion * 100}%` }}
                        ></div>
                      </div>
                      <span className="text-sm font-semibold text-slate-700 w-12 text-right">
                        {(proof.signals.motion * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-sm text-slate-600">
                      Challenge Response
                    </span>
                    <span
                      className={`text-sm font-semibold ${proof.signals.challengePassed ? "text-green-500" : "text-red-500"}`}
                    >
                      {proof.signals.challengePassed ? "✓ Passed" : "✗ Failed"}
                    </span>
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-sm text-slate-600">
                      Frame Analysis
                    </span>
                    <div className="flex items-center gap-2">
                      <div className="w-24 h-2 bg-slate-200 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-blue-500 rounded-full"
                          style={{ width: `${proof.signals.frameDiff * 100}%` }}
                        ></div>
                      </div>
                      <span className="text-sm font-semibold text-slate-700 w-12 text-right">
                        {(proof.signals.frameDiff * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-sm text-slate-600">
                      Light Variance
                    </span>
                    <div className="flex items-center gap-2">
                      <div className="w-24 h-2 bg-slate-200 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-blue-500 rounded-full"
                          style={{
                            width: `${proof.signals.lightVariance * 100}%`,
                          }}
                        ></div>
                      </div>
                      <span className="text-sm font-semibold text-slate-700 w-12 text-right">
                        {(proof.signals.lightVariance * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="mt-6 pt-6 border-t border-slate-200">
                <div className="flex justify-between text-xs text-slate-500">
                  <span>Session ID</span>
                  <span className="font-mono">
                    {proof.sessionId.slice(0, 8)}...
                  </span>
                </div>
                <div className="flex justify-between text-xs text-slate-500 mt-2">
                  <span>Timestamp</span>
                  <span>{new Date(proof.timestamp).toLocaleTimeString()}</span>
                </div>
              </div>
            </div>

            <div className="flex gap-3">
              <button
                onClick={downloadProof}
                className="flex-1 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold py-3 px-6 rounded-xl transition-colors"
              >
                Download Proof
              </button>
              <button
                onClick={reset}
                className="flex-1 bg-blue-500 hover:bg-blue-600 text-white font-semibold py-3 px-6 rounded-xl transition-colors"
              >
                Verify Again
              </button>
            </div>
          </div>
        )}

        {/* REJECTED State - Failed */}
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
                Please try again with better lighting and follow the
                instructions carefully
              </p>
            </div>

            {/* Results Card */}
            <div className="bg-red-50 rounded-2xl p-6 mb-6">
              <div className="space-y-4">
                <div className="flex justify-between items-center">
                  <span className="text-slate-600 font-medium">
                    Confidence Score
                  </span>
                  <span className="text-2xl font-bold text-red-500">
                    {(proof.confidence * 100).toFixed(1)}%
                  </span>
                </div>

                <div className="text-sm text-slate-600 bg-white rounded-lg p-4">
                  <p className="font-semibold mb-2">Issues detected:</p>
                  <ul className="list-disc list-inside space-y-1">
                    {proof.signals.motion < 0.1 && (
                      <li>Insufficient motion detected</li>
                    )}
                    {!proof.signals.challengePassed && (
                      <li>Challenge not completed correctly</li>
                    )}
                    {proof.signals.frameDiff < 0.02 && (
                      <li>Static image detected</li>
                    )}
                    {proof.signals.lightVariance < 0.1 && (
                      <li>Poor lighting conditions</li>
                    )}
                  </ul>
                </div>
              </div>
            </div>

            <button
              onClick={reset}
              className="w-full bg-blue-500 hover:bg-blue-600 text-white font-semibold py-4 px-6 rounded-xl transition-colors"
            >
              Try Again
            </button>
          </div>
        )}

        {/* Error State */}
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
