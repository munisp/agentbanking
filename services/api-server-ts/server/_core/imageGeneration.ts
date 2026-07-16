/**
 * imageGeneration.ts — Self-hosted image generation via OpenAI-compatible API.
 * No external platform dependency.
 *
 * Env vars:
 *   OPENAI_API_KEY  — API key (required)
 *   OPENAI_API_BASE — base URL (default: https://api.openai.com/v1)
 *   IMAGE_GEN_MODEL — model name (default: dall-e-3)
 */
import { storagePut } from "server/storage";

export type GenerateImageOptions = {
  prompt: string;
  originalImages?: Array<{ url?: string; b64Json?: string; mimeType?: string }>;
};
export type GenerateImageResponse = { url?: string };

export async function generateImage(
  options: GenerateImageOptions
): Promise<GenerateImageResponse> {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) throw new Error("OPENAI_API_KEY is not configured");

  const baseUrl = (process.env.OPENAI_API_BASE ?? "https://api.openai.com/v1").replace(/\/+$/, "");
  const model = process.env.IMAGE_GEN_MODEL ?? "dall-e-3";

  const response = await fetch(`${baseUrl}/images/generations`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      model,
      prompt: options.prompt,
      n: 1,
      size: "1024x1024",
      response_format: "b64_json",
    }),
  });

  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    throw new Error(`Image generation failed (${response.status}): ${detail}`);
  }

  const payload = await response.json();
  const b64 = payload?.data?.[0]?.b64_json as string | undefined;
  if (!b64) return {};

  const buffer = Buffer.from(b64, "base64");
  const key = `generated/${Date.now()}.png`;
  const { url } = await storagePut(key, buffer, "image/png");
  return { url };
}
