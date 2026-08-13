// @ts-nocheck
import type { ChallengeType as MotionChallengeType } from "./useFaceMotionDetection";
import { useFaceMotionDetection } from "../hooks/useFaceMotionDetection";
import { trpc } from "../lib/trpc";
import { useCallback, useRef, useState } from "react";
import { toast } from "sonner";
import { ScreenHeader } from "./POSShell.part10";
import { pickChallenges } from "./POSShell.part6";
import { BORDER, CARD, DISP, DocType, GOLD, GREEN, KycStep, MONO } from "./POSShell.shared";

function KYCVerifyScreen({ onBack }: { onBack: () => void }) {
  const [step, setStep] = useState<KycStep>("status");
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [challengeId, setChallengeId] = useState<string | null>(null);
  const [instruction, setInstruction] = useState("");
  const [docType, setDocType] = useState<DocType>("NIN");
  const [captureMode, setCaptureMode] = useState<"camera" | "upload">("camera");
  const [livenessResult, setLivenessResult] = useState<{
    passed: boolean;
    score: number;
  } | null>(null);
  const [ocrResult, setOcrResult] = useState<{
    name?: string | null;
    dob?: string | null;
    idNumber?: string | null;
    confidence: number;
    fraudIndicators: string[];
  } | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [cameraActive, setCameraActive] = useState(false);
  const [cameraError, setCameraError] = useState("");

  // ── Multi-challenge liveness state ──────────────────────────────────────
  const [challenges, setChallenges] = useState<
    Array<{
      type: MotionChallengeType;
      instruction: string;
      completed: boolean;
    }>
  >([]);
  const [currentChallengeIdx, setCurrentChallengeIdx] = useState(0);
  const [livenessActive, setLivenessActive] = useState(false);

  // Current challenge type for motion detection
  const currentChallengeType: MotionChallengeType | null =
    livenessActive &&
    challenges.length > 0 &&
    currentChallengeIdx < challenges.length
      ? challenges[currentChallengeIdx].type
      : null;

  // Handle motion detection callback
  const handleMotionDetected = useCallback(
    (type: MotionChallengeType, confidence: number) => {
      if (!livenessActive || currentChallengeIdx >= challenges.length) return;
      if (type !== challenges[currentChallengeIdx].type) return;

      // Mark current challenge as completed
      setChallenges(prev => {
        const updated = [...prev];
        if (currentChallengeIdx < updated.length) {
          updated[currentChallengeIdx] = {
            ...updated[currentChallengeIdx],
            completed: true,
          };
        }
        return updated;
      });

      const nextIdx = currentChallengeIdx + 1;
      if (nextIdx >= challenges.length) {
        // All challenges complete — auto-capture and submit
        setLivenessActive(false);
        autoSubmitLiveness();
      } else {
        setCurrentChallengeIdx(nextIdx);
      }
    },
    [livenessActive, currentChallengeIdx, challenges]
  );

  // Face motion detection hook
  const motionState = useFaceMotionDetection({
    videoRef,
    enabled: cameraActive && livenessActive && step === "liveness",
    activeChallenge: currentChallengeType,
    onChallengeDetected: handleMotionDetected,
    detectionIntervalMs: 100,
  });

  // Auto-submit liveness frame after all challenges pass
  const autoSubmitLiveness = useCallback(async () => {
    if (!videoRef.current || !canvasRef.current || !sessionId || !challengeId)
      return;
    const ctx = canvasRef.current.getContext("2d");
    if (!ctx) return;
    canvasRef.current.width = videoRef.current.videoWidth || 640;
    canvasRef.current.height = videoRef.current.videoHeight || 480;
    ctx.drawImage(videoRef.current, 0, 0);
    const frame = canvasRef.current.toDataURL("image/jpeg", 0.8).split(",")[1];
    try {
      const res = await submitFrame.mutateAsync({
        sessionId,
        challengeId,
        frameBase64: frame,
      });
      stopCamera();
      setLivenessResult({ passed: res.passed, score: res.score });
      if (res.passed) {
        toast.success("Liveness check passed!");
        setStep("document");
      } else {
        toast.error("Liveness check failed — please retry");
      }
    } catch {
      toast.error("Liveness verification error");
    }
  }, [sessionId, challengeId]);

  // Existing KYC status
  const { data: statusData, isLoading: statusLoading } =
    trpc.kyc.getStatus.useQuery();

  // Mutations
  const startLiveness = trpc.kyc.startLiveness.useMutation();
  const submitFrame = trpc.kyc.submitLivenessFrame.useMutation();
  const verifyDoc = trpc.kyc.verifyDocument.useMutation();

  // Start camera stream
  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user", width: 640, height: 480 },
      });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.play();
      }
      setCameraActive(true);
      setCameraError("");
    } catch {
      setCameraError(
        "Camera access denied. Please allow camera access or use file upload."
      );
    }
  };

  const stopCamera = () => {
    if (videoRef.current?.srcObject) {
      (videoRef.current.srcObject as MediaStream)
        .getTracks()
        .forEach(t => t.stop());
      videoRef.current.srcObject = null;
    }
    setCameraActive(false);
  };

  // Capture a frame from the camera as base64
  const captureFrame = (): string | null => {
    if (!videoRef.current || !canvasRef.current) return null;
    const ctx = canvasRef.current.getContext("2d");
    if (!ctx) return null;
    canvasRef.current.width = videoRef.current.videoWidth || 640;
    canvasRef.current.height = videoRef.current.videoHeight || 480;
    ctx.drawImage(videoRef.current, 0, 0);
    return canvasRef.current.toDataURL("image/jpeg", 0.8).split(",")[1];
  };

  // Read a file as base64
  const fileToBase64 = (file: File): Promise<string> =>
    new Promise((res, rej) => {
      const reader = new FileReader();
      reader.onload = () => res((reader.result as string).split(",")[1]);
      reader.onerror = rej;
      reader.readAsDataURL(file);
    });

  // ── Step: Status ──────────────────────────────────────────────────────────
  if (step === "status") {
    if (statusLoading)
      return (
        <div className="flex flex-col h-full">
          <ScreenHeader title="KYC Verification" onBack={onBack} />
          <div className="flex items-center justify-center flex-1">
            <div className="animate-spin text-3xl">⟳</div>
          </div>
        </div>
      );

    const existing = statusData?.session;
    const isComplete = existing?.status === "completed";

    return (
      <div className="flex flex-col h-full">
        <ScreenHeader
          title="KYC Verification"
          onBack={onBack}
          badge={
            <span
              className="text-xs px-2 py-0.5 rounded-full font-semibold"
              style={{
                background: "oklch(0.65 0.18 160 / 0.2)",
                color: GREEN,
                fontFamily: DISP,
              }}
            >
              BVN/NIN
            </span>
          }
        />
        <div className="flex flex-col gap-4 p-4">
          {existing && (
            <div
              className="rounded-2xl p-4 flex flex-col gap-2"
              style={{
                background: isComplete
                  ? "oklch(0.65 0.18 160 / 0.1)"
                  : "oklch(0.78 0.18 80 / 0.08)",
                border: `1px solid ${isComplete ? GREEN : GOLD}33`,
              }}
            >
              <div
                className="font-bold text-sm"
                style={{ color: isComplete ? GREEN : GOLD, fontFamily: DISP }}
              >
                Previous Session:{" "}
                {existing.status.replace(/_/g, " ").toUpperCase()}
              </div>
              {existing.docExtractedName && (
                <div className="text-xs text-gray-400">
                  Name:{" "}
                  <span className="text-white font-semibold">
                    {existing.docExtractedName}
                  </span>
                </div>
              )}
              {existing.docExtractedIdNumber && (
                <div className="text-xs text-gray-400">
                  ID:{" "}
                  <span className="text-white font-semibold">
                    {existing.docExtractedIdNumber}
                  </span>
                </div>
              )}
              {existing.livenessScore !== null && (
                <div className="text-xs text-gray-400">
                  Liveness Score:{" "}
                  <span className="text-white font-semibold">
                    {((existing.livenessScore ?? 0) * 100).toFixed(1)}%
                  </span>
                </div>
              )}
            </div>
          )}
          <div
            className="text-sm text-gray-400 leading-relaxed"
            style={{ fontFamily: DISP }}
          >
            This KYC flow uses our open-source engine:{" "}
            <strong className="text-white">liveness detection</strong>{" "}
            (challenge-response camera check) followed by{" "}
            <strong className="text-white">document OCR</strong> (PaddleOCR —
            NIN, BVN card, passport, drivers licence, voter card).
          </div>
          <button
            onClick={async () => {
              try {
                const res = await startLiveness.mutateAsync({
                  method: "active_blink",
                });
                setSessionId(res.sessionId);
                setChallengeId(res.challengeId);
                setInstruction(res.instruction);
                setStep("liveness");
                if (res.serviceAvailable) await startCamera();
              } catch {
                toast.error("Failed to start KYC session");
              }
            }}
            disabled={startLiveness.isPending}
            className="w-full py-4 rounded-xl font-bold text-white disabled:opacity-40"
            style={{ background: GREEN, fontFamily: DISP }}
          >
            {startLiveness.isPending
              ? "Starting..."
              : isComplete
                ? "Start New Verification"
                : "Begin KYC Verification"}
          </button>
        </div>
      </div>
    );
  }

  // ── Step: Liveness ────────────────────────────────────────────────────────
  if (step === "liveness") {
    // Start multi-challenge flow when entering liveness step
    if (!livenessActive && challenges.length === 0 && cameraActive) {
      const picked = pickChallenges(3);
      setChallenges(picked);
      setCurrentChallengeIdx(0);
      setLivenessActive(true);
    }

    const currentChallenge =
      challenges.length > 0 && currentChallengeIdx < challenges.length
        ? challenges[currentChallengeIdx]
        : null;

    return (
      <div className="flex flex-col h-full">
        <ScreenHeader
          title="Liveness Check"
          onBack={() => {
            stopCamera();
            setLivenessActive(false);
            setChallenges([]);
            setCurrentChallengeIdx(0);
            setStep("status");
          }}
        />
        <div className="flex flex-col gap-4 p-4">
          {/* Challenge instruction */}
          <div
            className="rounded-2xl p-3 text-center"
            style={{
              background: "oklch(0.55 0.22 300 / 0.15)",
              fontFamily: DISP,
            }}
          >
            {livenessActive && currentChallenge ? (
              <>
                <div className="text-xs mb-1" style={{ color: "#a78bfa99" }}>
                  Challenge {currentChallengeIdx + 1} of {challenges.length}
                </div>
                <div className="text-sm font-bold" style={{ color: "#a78bfa" }}>
                  {currentChallenge.instruction}
                </div>
                <div className="text-xs mt-1" style={{ color: "#a78bfa77" }}>
                  {motionState.ready
                    ? "Motion will be detected automatically"
                    : "Loading face detection..."}
                </div>
              </>
            ) : (
              <div
                className="text-sm font-semibold"
                style={{ color: "#a78bfa" }}
              >
                {instruction ||
                  "Position your face in the frame and follow the instruction"}
              </div>
            )}
          </div>

          {/* Challenge progress dots */}
          {livenessActive && challenges.length > 0 && (
            <div className="flex items-center justify-center gap-2">
              {challenges.map((c, i) => (
                <div
                  key={i}
                  className="w-3 h-3 rounded-full transition-all"
                  style={{
                    background:
                      i < currentChallengeIdx
                        ? c.completed
                          ? GREEN
                          : "#ef4444"
                        : i === currentChallengeIdx
                          ? "#facc15"
                          : "oklch(0.3 0.01 230)",
                    boxShadow:
                      i === currentChallengeIdx ? "0 0 8px #facc1566" : "none",
                  }}
                />
              ))}
            </div>
          )}

          {/* Camera preview */}
          <div
            className="relative rounded-2xl overflow-hidden"
            style={{
              background: CARD,
              border: `1px solid ${BORDER}`,
              aspectRatio: "4/3",
            }}
          >
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className="w-full h-full object-cover"
            />
            <canvas ref={canvasRef} className="hidden" />
            {!cameraActive && (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-3">
                {cameraError ? (
                  <div className="text-xs text-red-400 text-center px-4">
                    {cameraError}
                  </div>
                ) : null}
                <button
                  onClick={startCamera}
                  className="px-4 py-2 rounded-xl text-sm font-semibold text-white"
                  style={{ background: "#8b5cf6" }}
                >
                  Enable Camera
                </button>
              </div>
            )}
          </div>

          {/* Face detection status & real-time metrics */}
          {livenessActive && cameraActive && (
            <div
              className="rounded-xl p-3 flex items-center gap-3"
              style={{
                background: "oklch(0.15 0.01 230)",
                border: `1px solid ${BORDER}`,
              }}
            >
              {motionState.ready ? (
                <>
                  <div
                    className="w-3 h-3 rounded-full"
                    style={{
                      background: motionState.faceDetected ? GREEN : "#facc15",
                      boxShadow: motionState.faceDetected
                        ? `0 0 8px ${GREEN}66`
                        : "0 0 8px #facc1544",
                      animation: motionState.faceDetected
                        ? "none"
                        : "pulse 1.5s infinite",
                    }}
                  />
                  <div className="flex-1">
                    <div
                      className="text-xs font-semibold"
                      style={{
                        color: motionState.faceDetected ? GREEN : GOLD,
                        fontFamily: DISP,
                      }}
                    >
                      {motionState.faceDetected
                        ? "Face detected — perform the action"
                        : "Position your face in the frame"}
                    </div>
                    {motionState.faceDetected && currentChallengeType && (
                      <div
                        className="text-[10px] mt-0.5"
                        style={{ color: "oklch(0.55 0.01 230)" }}
                      >
                        {currentChallengeType === "blink" &&
                          `Eye openness: ${(motionState.metrics.ear * 100).toFixed(0)}%`}
                        {(currentChallengeType === "turn_left" ||
                          currentChallengeType === "turn_right") &&
                          `Head angle: ${motionState.metrics.yaw.toFixed(1)}°`}
                        {currentChallengeType === "nod" &&
                          `Head pitch: ${motionState.metrics.pitch.toFixed(1)}°`}
                        {currentChallengeType === "smile" &&
                          `Smile: ${((motionState.metrics.smileRatio / 4) * 100).toFixed(0)}%`}
                        {currentChallengeType === "open_mouth" &&
                          `Mouth: ${(motionState.metrics.mar * 100).toFixed(0)}%`}
                      </div>
                    )}
                  </div>
                </>
              ) : (
                <>
                  <div className="animate-spin text-sm">⟳</div>
                  <div
                    className="text-xs"
                    style={{ color: "oklch(0.55 0.01 230)", fontFamily: DISP }}
                  >
                    Loading face detection model...
                  </div>
                </>
              )}
            </div>
          )}

          {/* Manual capture fallback + skip */}
          <div className="flex gap-2">
            <button
              onClick={async () => {
                const frame = captureFrame();
                if (!frame) {
                  toast.error("No frame captured — enable camera first");
                  return;
                }
                if (!sessionId || !challengeId) {
                  toast.error("Session not initialised");
                  return;
                }
                try {
                  const res = await submitFrame.mutateAsync({
                    sessionId,
                    challengeId,
                    frameBase64: frame,
                  });
                  stopCamera();
                  setLivenessActive(false);
                  setLivenessResult({ passed: res.passed, score: res.score });
                  if (res.passed) {
                    toast.success("Liveness check passed!");
                    setStep("document");
                  } else {
                    toast.error("Liveness check failed — please retry");
                  }
                } catch {
                  toast.error("Liveness verification error");
                }
              }}
              disabled={!cameraActive || submitFrame.isPending}
              className="flex-1 py-3 rounded-xl font-bold text-white disabled:opacity-40 text-sm"
              style={{ background: "#8b5cf6", fontFamily: DISP }}
            >
              {submitFrame.isPending
                ? "Verifying..."
                : "Manual Capture & Verify"}
            </button>
            {livenessActive && (
              <button
                onClick={() => {
                  // Skip current challenge
                  const nextIdx = currentChallengeIdx + 1;
                  if (nextIdx >= challenges.length) {
                    setLivenessActive(false);
                    autoSubmitLiveness();
                  } else {
                    setCurrentChallengeIdx(nextIdx);
                  }
                }}
                className="py-3 px-4 rounded-xl text-xs font-semibold"
                style={{
                  background: CARD,
                  color: "oklch(0.55 0.01 230)",
                  border: `1px solid ${BORDER}`,
                  fontFamily: DISP,
                }}
              >
                Skip
              </button>
            )}
          </div>

          {livenessResult && !livenessResult.passed && (
            <div
              className="text-center text-red-400 text-sm"
              style={{ fontFamily: DISP }}
            >
              Score: {(livenessResult.score * 100).toFixed(1)}% — Minimum 60%
              required
            </div>
          )}

          {/* Skip liveness if service unavailable */}
          {!challengeId && (
            <button
              onClick={() => {
                stopCamera();
                setLivenessActive(false);
                setStep("document");
              }}
              className="w-full py-3 rounded-xl text-sm font-semibold"
              style={{
                background: CARD,
                color: GOLD,
                border: `1px solid ${BORDER}`,
                fontFamily: DISP,
              }}
            >
              Skip (Liveness Service Unavailable)
            </button>
          )}
        </div>
      </div>
    );
  }

  // ── Step: Document OCR ────────────────────────────────────────────────────
  if (step === "document") {
    return (
      <div className="flex flex-col h-full">
        <ScreenHeader
          title="Document Verification"
          onBack={() => setStep("liveness")}
        />
        <div className="flex flex-col gap-4 p-4">
          <div className="text-xs text-gray-400" style={{ fontFamily: DISP }}>
            Select document type
          </div>
          <div className="grid grid-cols-2 gap-2">
            {(
              [
                "NIN",
                "BVN_CARD",
                "PASSPORT",
                "DRIVERS_LICENCE",
                "VOTER_CARD",
              ] as DocType[]
            ).map(dt => (
              <button
                key={dt}
                onClick={() => setDocType(dt)}
                className="py-2 px-3 rounded-xl text-xs font-semibold transition-all"
                style={{
                  background:
                    docType === dt ? "oklch(0.65 0.18 160 / 0.3)" : CARD,
                  color: docType === dt ? GREEN : "oklch(0.55 0.015 230)",
                  border: `1px solid ${docType === dt ? GREEN : BORDER}`,
                  fontFamily: DISP,
                }}
              >
                {dt.replace("_", " ")}
              </button>
            ))}
          </div>

          <div className="flex gap-2">
            {(["camera", "upload"] as const).map(m => (
              <button
                key={m}
                onClick={() => {
                  setCaptureMode(m);
                  if (m === "camera") startCamera();
                  else stopCamera();
                }}
                className="flex-1 py-2 rounded-xl text-xs font-semibold"
                style={{
                  background:
                    captureMode === m ? "oklch(0.55 0.22 300 / 0.3)" : CARD,
                  color:
                    captureMode === m ? "#a78bfa" : "oklch(0.55 0.015 230)",
                  fontFamily: DISP,
                }}
              >
                {m === "camera" ? "📷 Camera" : "📁 Upload File"}
              </button>
            ))}
          </div>

          {captureMode === "camera" ? (
            <div
              className="relative rounded-2xl overflow-hidden"
              style={{
                background: CARD,
                border: `1px solid ${BORDER}`,
                aspectRatio: "4/3",
              }}
            >
              <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                className="w-full h-full object-cover"
              />
              <canvas ref={canvasRef} className="hidden" />
              {!cameraActive && (
                <div className="absolute inset-0 flex items-center justify-center">
                  <button
                    onClick={startCamera}
                    className="px-4 py-2 rounded-xl text-sm font-semibold text-white"
                    style={{ background: "#8b5cf6" }}
                  >
                    Enable Camera
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div
              className="rounded-2xl p-6 flex flex-col items-center gap-3"
              style={{ background: CARD, border: `2px dashed ${BORDER}` }}
            >
              <div className="text-3xl">📄</div>
              <div
                className="text-xs text-gray-400"
                style={{ fontFamily: DISP }}
              >
                Tap to select document image
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={async e => {
                  const file = e.target.files?.[0];
                  if (!file || !sessionId) return;
                  try {
                    const b64 = await fileToBase64(file);
                    const res = await verifyDoc.mutateAsync({
                      sessionId,
                      imageBase64: b64,
                      docType,
                    });
                    setOcrResult({
                      name: res.extractedName,
                      dob: res.extractedDob,
                      idNumber: res.extractedIdNumber,
                      confidence: res.confidence,
                      fraudIndicators: res.fraudIndicators,
                    });
                    if (res.passed) {
                      toast.success("Document verified!");
                      setStep("complete");
                    } else {
                      toast.error(
                        `Document verification failed (confidence: ${(res.confidence * 100).toFixed(0)}%)`
                      );
                    }
                  } catch {
                    toast.error("Document processing error");
                  }
                }}
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                className="px-4 py-2 rounded-xl text-sm font-semibold text-white"
                style={{ background: GREEN, fontFamily: DISP }}
              >
                Choose File
              </button>
            </div>
          )}

          {captureMode === "camera" && (
            <button
              onClick={async () => {
                const frame = captureFrame();
                if (!frame || !sessionId) {
                  toast.error("No frame captured");
                  return;
                }
                try {
                  const res = await verifyDoc.mutateAsync({
                    sessionId,
                    imageBase64: frame,
                    docType,
                  });
                  stopCamera();
                  setOcrResult({
                    name: res.extractedName,
                    dob: res.extractedDob,
                    idNumber: res.extractedIdNumber,
                    confidence: res.confidence,
                    fraudIndicators: res.fraudIndicators,
                  });
                  if (res.passed) {
                    toast.success("Document verified!");
                    setStep("complete");
                  } else {
                    toast.error(
                      `Verification failed — confidence: ${(res.confidence * 100).toFixed(0)}%`
                    );
                  }
                } catch {
                  toast.error("Document processing error");
                }
              }}
              disabled={!cameraActive || verifyDoc.isPending}
              className="w-full py-4 rounded-xl font-bold text-white disabled:opacity-40"
              style={{ background: GREEN, fontFamily: DISP }}
            >
              {verifyDoc.isPending ? "Processing..." : "Capture Document"}
            </button>
          )}
        </div>
      </div>
    );
  }

  // ── Step: Complete ────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col h-full">
      <ScreenHeader title="KYC Complete" onBack={onBack} />
      <div className="flex flex-col gap-4 p-4">
        <div
          className="rounded-2xl p-5 flex flex-col gap-3"
          style={{
            background: "oklch(0.65 0.18 160 / 0.1)",
            border: `1px solid ${GREEN}33`,
          }}
        >
          <div className="flex items-center gap-3">
            <div
              className="w-10 h-10 rounded-full flex items-center justify-center text-xl"
              style={{ background: "oklch(0.65 0.18 160 / 0.3)" }}
            >
              ✓
            </div>
            <div>
              <div
                className="font-bold text-green-400"
                style={{ fontFamily: DISP }}
              >
                Identity Verified
              </div>
              <div className="text-xs text-gray-500">
                Liveness + Document OCR passed
              </div>
            </div>
          </div>
          {ocrResult && (
            <>
              {ocrResult.name && (
                <div className="flex justify-between">
                  <span
                    className="text-xs text-gray-500"
                    style={{ fontFamily: DISP }}
                  >
                    Full Name
                  </span>
                  <span
                    className="text-xs font-bold text-white"
                    style={{ fontFamily: MONO }}
                  >
                    {ocrResult.name}
                  </span>
                </div>
              )}
              {ocrResult.dob && (
                <div className="flex justify-between">
                  <span
                    className="text-xs text-gray-500"
                    style={{ fontFamily: DISP }}
                  >
                    Date of Birth
                  </span>
                  <span
                    className="text-xs font-bold text-white"
                    style={{ fontFamily: MONO }}
                  >
                    {ocrResult.dob}
                  </span>
                </div>
              )}
              {ocrResult.idNumber && (
                <div className="flex justify-between">
                  <span
                    className="text-xs text-gray-500"
                    style={{ fontFamily: DISP }}
                  >
                    ID Number
                  </span>
                  <span
                    className="text-xs font-bold text-white"
                    style={{ fontFamily: MONO }}
                  >
                    {ocrResult.idNumber}
                  </span>
                </div>
              )}
              <div className="flex justify-between">
                <span
                  className="text-xs text-gray-500"
                  style={{ fontFamily: DISP }}
                >
                  OCR Confidence
                </span>
                <span
                  className="text-xs font-bold"
                  style={{ color: GREEN, fontFamily: MONO }}
                >
                  {(ocrResult.confidence * 100).toFixed(1)}%
                </span>
              </div>
              {ocrResult.fraudIndicators.length > 0 && (
                <div
                  className="text-xs text-red-400"
                  style={{ fontFamily: DISP }}
                >
                  ⚠ Fraud indicators: {ocrResult.fraudIndicators.join(", ")}
                </div>
              )}
            </>
          )}
          {livenessResult && (
            <div className="flex justify-between">
              <span
                className="text-xs text-gray-500"
                style={{ fontFamily: DISP }}
              >
                Liveness Score
              </span>
              <span
                className="text-xs font-bold"
                style={{ color: GREEN, fontFamily: MONO }}
              >
                {(livenessResult.score * 100).toFixed(1)}%
              </span>
            </div>
          )}
        </div>
        <button
          onClick={() => {
            setStep("status");
            setOcrResult(null);
            setLivenessResult(null);
            toast.success("KYC session saved");
          }}
          className="w-full py-4 rounded-xl font-bold text-white"
          style={{ background: GREEN, fontFamily: DISP }}
        >
          Done
        </button>
      </div>
    </div>
  );
}

// 12. Biometric ───────────────────────────────────────────────────────────────

function CarrierSwitchScreen({ onBack }: { onBack: () => void }) {
  const BG2 = "#0a0e1a";
  const CARD2 = "oklch(0.14 0.02 240)";
  const BORDER2 = "oklch(0.22 0.02 240)";
  const GREEN2 = "oklch(0.65 0.18 160)";
  const BLUE2 = "oklch(0.60 0.22 260)";
  const GOLD2 = "oklch(0.78 0.18 80)";
  const RED2 = "oklch(0.60 0.22 25)";
  const CYAN2 = "oklch(0.65 0.18 200)";
  const DISP2 = "'Space Grotesk', sans-serif";
  const MONO2 = "'JetBrains Mono', monospace";

  const [currentCarrier, setCurrentCarrier] = useState("MTN");
  const [autoSwitch, setAutoSwitch] = useState(false);

  const rankings = trpc.carrierSwitching.getRankings.useQuery();
  const recommendation = trpc.carrierSwitching.getRecommendation.useQuery({
    currentCarrier,
  });
  const switchStats = trpc.carrierSwitching.getSwitchStats.useQuery();
  const recordSwitch = trpc.carrierSwitching.recordSwitch.useMutation({
    onSuccess: () => {
      rankings.refetch();
      recommendation.refetch();
      switchStats.refetch();
    },
  });

  const handleSwitch = async (toCarrier: string) => {
    if (toCarrier === currentCarrier) return;
    try {
      await recordSwitch.mutateAsync({
        fromCarrier: currentCarrier,
        toCarrier,
        agentCode: "AGT-NG-0042",
        reason: "Manual switch from CarrierSwitch screen",
        autoTriggered: false,
      });
      setCurrentCarrier(toCarrier);
      toast.success(`Switched to ${toCarrier}`);
    } catch {
      toast.error("Switch failed");
    }
  };

  const gradeColor = (grade: string) => {
    if (grade === "A+" || grade === "A") return GREEN2;
    if (grade === "B") return BLUE2;
    if (grade === "C") return GOLD2;
    return RED2;
  };

  const barColor = (bars: number) => {
    if (bars >= 4) return GREEN2;
    if (bars >= 3) return BLUE2;
    if (bars >= 2) return GOLD2;
    return RED2;
  };

  return (
    <div className="flex flex-col h-screen" style={{ background: BG2 }}>
      <ScreenHeader
        title="📡 Carrier Switch"
        onBack={onBack}
        badge={
          <div className="flex items-center gap-2">
            <span
              className="text-xs px-2 py-1 rounded-full"
              style={{
                background: `${CYAN2}20`,
                color: CYAN2,
                fontFamily: MONO2,
              }}
            >
              {currentCarrier}
            </span>
          </div>
        }
      />
      <div className="flex-1 overflow-y-auto p-4">
        {/* Auto-switch recommendation */}
        {recommendation.data?.shouldSwitch && (
          <div
            className="rounded-2xl p-4 mb-4"
            style={{
              background: `${GREEN2}10`,
              border: `1px solid ${GREEN2}30`,
            }}
          >
            <div className="flex items-center gap-3">
              <div className="text-2xl">⚡</div>
              <div className="flex-1">
                <div
                  className="text-sm font-bold text-white"
                  style={{ fontFamily: DISP2 }}
                >
                  Switch Recommended
                </div>
                <div className="text-xs text-gray-400 mt-0.5">
                  {recommendation.data.reason}
                </div>
              </div>
              <button
                onClick={() => handleSwitch(recommendation.data!.bestCarrier!)}
                disabled={recordSwitch.isPending}
                className="px-3 py-2 rounded-xl text-xs font-bold disabled:opacity-50"
                style={{ background: GREEN2, color: "white" }}
              >
                {recordSwitch.isPending ? "…" : "Switch"}
              </button>
            </div>
            <div className="flex items-center gap-4 mt-3">
              <div
                className="flex-1 rounded-lg p-2 text-center"
                style={{ background: `${RED2}15` }}
              >
                <div className="text-xs text-gray-500">Current</div>
                <div
                  className="text-sm font-bold"
                  style={{ color: RED2, fontFamily: MONO2 }}
                >
                  {recommendation.data.currentScore}
                </div>
              </div>
              <div className="text-gray-600">→</div>
              <div
                className="flex-1 rounded-lg p-2 text-center"
                style={{ background: `${GREEN2}15` }}
              >
                <div className="text-xs text-gray-500">Best</div>
                <div
                  className="text-sm font-bold"
                  style={{ color: GREEN2, fontFamily: MONO2 }}
                >
                  {recommendation.data.bestScore}
                </div>
              </div>
              <div
                className="flex-1 rounded-lg p-2 text-center"
                style={{ background: `${BLUE2}15` }}
              >
                <div className="text-xs text-gray-500">Gain</div>
                <div
                  className="text-sm font-bold"
                  style={{ color: BLUE2, fontFamily: MONO2 }}
                >
                  +{recommendation.data.improvement}%
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Current carrier */}
        <div
          className="rounded-2xl p-4 mb-4"
          style={{ background: CARD2, border: `1px solid ${BORDER2}` }}
        >
          <div className="flex items-center justify-between mb-3">
            <div
              className="text-xs text-gray-500"
              style={{ fontFamily: DISP2 }}
            >
              Active Carrier
            </div>
            <div className="flex items-center gap-1">
              <span className="text-xs text-gray-500">Auto-Switch</span>
              <button
                onClick={() => setAutoSwitch(!autoSwitch)}
                className="w-10 h-5 rounded-full transition-all relative"
                style={{ background: autoSwitch ? GREEN2 : BORDER2 }}
              >
                <div
                  className="w-4 h-4 rounded-full bg-white absolute top-0.5 transition-all"
                  style={{ left: autoSwitch ? "22px" : "2px" }}
                />
              </button>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div
              className="w-12 h-12 rounded-xl flex items-center justify-center text-2xl"
              style={{ background: `${CYAN2}15` }}
            >
              📡
            </div>
            <div className="flex-1">
              <div
                className="text-lg font-bold text-white"
                style={{ fontFamily: DISP2 }}
              >
                {currentCarrier}
              </div>
              <div className="text-xs text-gray-500">
                Score:{" "}
                <span style={{ color: GREEN2 }}>
                  {recommendation.data?.currentScore || "—"}
                </span>
              </div>
            </div>
            {/* Signal bars */}
            <div className="flex items-end gap-0.5 h-6">
              {[1, 2, 3, 4, 5].map(bar => {
                const active =
                  (rankings.data?.find(r => r.name === currentCarrier)
                    ?.signalBars || 3) >= bar;
                return (
                  <div
                    key={bar}
                    className="w-1.5 rounded-sm transition-all"
                    style={{
                      height: `${bar * 4 + 4}px`,
                      background: active
                        ? barColor(
                            rankings.data?.find(r => r.name === currentCarrier)
                              ?.signalBars || 3
                          )
                        : BORDER2,
                    }}
                  />
                );
              })}
            </div>
          </div>
        </div>

        {/* Carrier rankings */}
        <div className="mb-4">
          <div
            className="text-xs text-gray-500 mb-2"
            style={{ fontFamily: DISP2 }}
          >
            Carrier Rankings
          </div>
          {(rankings.data || []).map((carrier: any) => (
            <div
              key={carrier.name}
              className="rounded-xl p-3 mb-2 flex items-center gap-3 transition-all"
              style={{
                background:
                  carrier.name === currentCarrier ? `${CYAN2}10` : CARD2,
                border: `1px solid ${carrier.name === currentCarrier ? `${CYAN2}40` : BORDER2}`,
              }}
            >
              {/* Rank */}
              <div
                className="w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold"
                style={{
                  background: `${gradeColor(carrier.grade)}20`,
                  color: gradeColor(carrier.grade),
                  fontFamily: MONO2,
                }}
              >
                {carrier.rank}
              </div>
              {/* Info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span
                    className="text-sm font-bold text-white truncate"
                    style={{ fontFamily: DISP2 }}
                  >
                    {carrier.name}
                  </span>
                  <span
                    className="text-[10px] px-1.5 py-0.5 rounded-full font-bold"
                    style={{
                      background: `${gradeColor(carrier.grade)}20`,
                      color: gradeColor(carrier.grade),
                    }}
                  >
                    {carrier.grade}
                  </span>
                  {carrier.name === currentCarrier && (
                    <span
                      className="text-[10px] px-1.5 py-0.5 rounded-full"
                      style={{ background: `${CYAN2}20`, color: CYAN2 }}
                    >
                      ACTIVE
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-3 mt-1">
                  <span className="text-[10px] text-gray-500">
                    {carrier.technology}
                  </span>
                  <span className="text-[10px] text-gray-500">
                    {carrier.signalDbm.toFixed(0)} dBm
                  </span>
                  <span className="text-[10px] text-gray-500">
                    {carrier.latencyMs.toFixed(0)}ms
                  </span>
                </div>
              </div>
              {/* Signal bars */}
              <div className="flex items-end gap-0.5 h-5">
                {[1, 2, 3, 4, 5].map(bar => (
                  <div
                    key={bar}
                    className="w-1 rounded-sm"
                    style={{
                      height: `${bar * 3 + 3}px`,
                      background:
                        carrier.signalBars >= bar
                          ? barColor(carrier.signalBars)
                          : BORDER2,
                    }}
                  />
                ))}
              </div>
              {/* Quality score */}
              <div className="text-right">
                <div
                  className="text-sm font-bold"
                  style={{
                    color: gradeColor(carrier.grade),
                    fontFamily: MONO2,
                  }}
                >
                  {carrier.qualityScore.toFixed(0)}
                </div>
              </div>
              {/* Switch button */}
              {carrier.name !== currentCarrier && carrier.sampleCount > 0 && (
                <button
                  onClick={() => handleSwitch(carrier.name)}
                  disabled={recordSwitch.isPending}
                  className="px-2 py-1.5 rounded-lg text-[10px] font-bold disabled:opacity-50"
                  style={{
                    background: `${BLUE2}20`,
                    color: BLUE2,
                    border: `1px solid ${BLUE2}30`,
                  }}
                >
                  Switch
                </button>
              )}
            </div>
          ))}
        </div>

        {/* Switch stats */}
        {switchStats.data && (
          <div className="mb-4">
            <div
              className="text-xs text-gray-500 mb-2"
              style={{ fontFamily: DISP2 }}
            >
              Switch Statistics
            </div>
            <div className="grid grid-cols-2 gap-2">
              {[
                {
                  label: "Total Switches",
                  value: switchStats.data.totalSwitches,
                  color: BLUE2,
                },
                {
                  label: "Auto Switches",
                  value: switchStats.data.autoSwitches,
                  color: CYAN2,
                },
                {
                  label: "Manual",
                  value: switchStats.data.manualSwitches,
                  color: GOLD2,
                },
                {
                  label: "Avg Improvement",
                  value: `${switchStats.data.avgImprovement}%`,
                  color: GREEN2,
                },
              ].map((s, i) => (
                <div
                  key={i}
                  className="rounded-xl p-3"
                  style={{ background: CARD2, border: `1px solid ${BORDER2}` }}
                >
                  <div
                    className="text-lg font-bold"
                    style={{ color: s.color, fontFamily: MONO2 }}
                  >
                    {s.value}
                  </div>
                  <div className="text-[10px] text-gray-500">{s.label}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Recent switches */}
        {switchStats.data?.recentSwitches &&
          switchStats.data.recentSwitches.length > 0 && (
            <div>
              <div
                className="text-xs text-gray-500 mb-2"
                style={{ fontFamily: DISP2 }}
              >
                Recent Switches
              </div>
              {switchStats.data.recentSwitches.map((sw, i) => (
                <div
                  key={i}
                  className="rounded-xl p-3 mb-2 flex items-center gap-3"
                  style={{ background: CARD2, border: `1px solid ${BORDER2}` }}
                >
                  <div
                    className="text-xs font-bold"
                    style={{ color: RED2, fontFamily: MONO2 }}
                  >
                    {sw.fromCarrier}
                  </div>
                  <div className="text-gray-600">→</div>
                  <div
                    className="text-xs font-bold"
                    style={{ color: GREEN2, fontFamily: MONO2 }}
                  >
                    {sw.toCarrier}
                  </div>
                  <div className="flex-1 text-right">
                    <div
                      className="text-[10px]"
                      style={{ color: sw.improvement > 0 ? GREEN2 : RED2 }}
                    >
                      {sw.improvement > 0 ? "+" : ""}
                      {sw.improvement}%
                    </div>
                    <div className="text-[10px] text-gray-600">
                      {sw.autoTriggered ? "auto" : "manual"}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
      </div>
    </div>
  );
}

