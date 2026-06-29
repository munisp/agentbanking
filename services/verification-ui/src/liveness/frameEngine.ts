/**
 * Frame Engine
 * Handles frame capture, canvas drawing, and frame buffers
 */

import type { FrameData } from "./types";

export function captureFrame(
  video: HTMLVideoElement,
  canvas: HTMLCanvasElement,
  ctx: CanvasRenderingContext2D,
): FrameData {
  // Ensure canvas matches video dimensions
  if (
    canvas.width !== video.videoWidth ||
    canvas.height !== video.videoHeight
  ) {
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
  }

  // Draw current video frame to canvas
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

  // Get image data
  const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);

  return {
    imageData,
    timestamp: Date.now(),
  };
}

export function createFrameBuffer(): FrameData[] {
  return [];
}

export function addToBuffer(
  buffer: FrameData[],
  frame: FrameData,
  maxSize: number = 10,
): FrameData[] {
  const newBuffer = [...buffer, frame];
  if (newBuffer.length > maxSize) {
    newBuffer.shift();
  }
  return newBuffer;
}

export function getAverageFrameData(buffer: FrameData[]): ImageData | null {
  if (buffer.length === 0) return null;

  const first = buffer[0].imageData;
  const averaged = new ImageData(first.width, first.height);

  // Average pixel values across all frames
  for (let i = 0; i < first.data.length; i++) {
    let sum = 0;
    buffer.forEach((frame) => {
      sum += frame.imageData.data[i];
    });
    averaged.data[i] = sum / buffer.length;
  }

  return averaged;
}
