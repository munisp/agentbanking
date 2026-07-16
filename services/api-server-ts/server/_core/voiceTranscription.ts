/**
 * voiceTranscription.ts — Self-hosted speech-to-text via OpenAI Whisper API.
 * No external platform dependency.
 *
 * Env vars:
 *   OPENAI_API_KEY  — API key (required)
 *   OPENAI_API_BASE — base URL (default: https://api.openai.com/v1)
 */
export type WhisperSegment = {
  id: number; seek: number; start: number; end: number; text: string;
  tokens: number[]; temperature: number; avg_logprob: number;
  compression_ratio: number; no_speech_prob: number;
};

export type TranscribeOptions = {
  audioUrl: string;
  language?: string;
  prompt?: string;
};

export type TranscribeResponse = {
  text: string;
  language?: string;
  duration?: number;
  segments?: WhisperSegment[];
};

export async function transcribeAudio(
  options: TranscribeOptions
): Promise<TranscribeResponse> {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) throw new Error("OPENAI_API_KEY is not configured");

  const baseUrl = (process.env.OPENAI_API_BASE ?? "https://api.openai.com/v1").replace(/\/+$/, "");

  // Fetch the audio file from the URL
  const audioResponse = await fetch(options.audioUrl);
  if (!audioResponse.ok) throw new Error(`Failed to fetch audio from ${options.audioUrl}`);
  const audioBuffer = await audioResponse.arrayBuffer();
  const audioBlob = new Blob([audioBuffer], { type: "audio/mpeg" });

  const formData = new FormData();
  formData.append("file", audioBlob, "audio.mp3");
  formData.append("model", "whisper-1");
  formData.append("response_format", "verbose_json");
  if (options.language) formData.append("language", options.language);
  if (options.prompt) formData.append("prompt", options.prompt);

  const response = await fetch(`${baseUrl}/audio/transcriptions`, {
    method: "POST",
    headers: { authorization: `Bearer ${apiKey}` },
    body: formData,
  });

  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    throw new Error(`Transcription failed (${response.status}): ${detail}`);
  }

  const payload = await response.json();
  return {
    text: payload.text ?? "",
    language: payload.language,
    duration: payload.duration,
    segments: payload.segments,
  };
}
