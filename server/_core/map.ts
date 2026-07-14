/**
 * map.ts — Self-hosted geocoding/maps via OpenStreetMap Nominatim.
 * No external platform dependency.
 *
 * Uses the free OpenStreetMap Nominatim API for geocoding.
 * For production, consider self-hosting Nominatim or using a paid provider
 * with env var GEOCODING_API_KEY.
 *
 * Env vars (optional, for paid providers):
 *   GEOCODING_PROVIDER — "nominatim" (default) | "google" | "here"
 *   GEOCODING_API_KEY  — API key for paid providers
 */

export type GeocodingResult = {
  lat: number;
  lon: number;
  displayName: string;
  country?: string;
  state?: string;
  city?: string;
};

export async function geocodeAddress(
  address: string
): Promise<GeocodingResult | null> {
  const provider = process.env.GEOCODING_PROVIDER ?? "nominatim";

  if (provider === "nominatim") {
    return geocodeNominatim(address);
  }

  console.warn(`[Map] Unsupported geocoding provider: ${provider}`);
  return null;
}

async function geocodeNominatim(
  address: string
): Promise<GeocodingResult | null> {
  const url = `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(address)}&format=json&limit=1&addressdetails=1`;
  try {
    const response = await fetch(url, {
      headers: { "User-Agent": "54Link-AgentBanking/1.0" },
      signal: AbortSignal.timeout(5_000),
    });
    if (!response.ok) return null;
    const results = await response.json();
    if (!results?.length) return null;
    const r = results[0];
    return {
      lat: parseFloat(r.lat),
      lon: parseFloat(r.lon),
      displayName: r.display_name,
      country: r.address?.country,
      state: r.address?.state,
      city: r.address?.city ?? r.address?.town ?? r.address?.village,
    };
  } catch {
    return null;
  }
}

export async function reverseGeocode(
  lat: number,
  lon: number
): Promise<GeocodingResult | null> {
  const url = `https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lon}&format=json&addressdetails=1`;
  try {
    const response = await fetch(url, {
      headers: { "User-Agent": "54Link-AgentBanking/1.0" },
      signal: AbortSignal.timeout(5_000),
    });
    if (!response.ok) return null;
    const r = await response.json();
    return {
      lat,
      lon,
      displayName: r.display_name,
      country: r.address?.country,
      state: r.address?.state,
      city: r.address?.city ?? r.address?.town ?? r.address?.village,
    };
  } catch {
    return null;
  }
}
