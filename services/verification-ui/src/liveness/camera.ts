/**
 * Camera Module
 * Handles camera access, stream lifecycle, and permissions
 */

export async function initCamera(
  videoElement: HTMLVideoElement,
): Promise<MediaStream> {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: {
        width: { ideal: 1280 },
        height: { ideal: 720 },
        facingMode: "user",
      },
      audio: false,
    });

    videoElement.srcObject = stream;

    // Wait for video to be ready
    return new Promise((resolve, reject) => {
      videoElement.onloadedmetadata = () => {
        videoElement
          .play()
          .then(() => resolve(stream))
          .catch(reject);
      };
    });
  } catch (error) {
    console.error("Camera initialization failed:", error);
    throw new Error("Camera access denied or unavailable");
  }
}

export function stopCamera(stream: MediaStream | null): void {
  if (stream) {
    stream.getTracks().forEach((track) => track.stop());
  }
}

export function isCameraAvailable(): boolean {
  return !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
}
