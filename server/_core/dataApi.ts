/**
 * dataApi.ts — Generic external API proxy helper.
 * No external platform dependency.
 *
 * Replaces the legacy CallApi proxy with direct HTTP calls.
 * Callers should use specific service clients (e.g. stripe, twilio) instead
 * of this generic helper where possible.
 */
export type DataApiCallOptions = {
  query?: Record<string, unknown>;
  body?: Record<string, unknown>;
  pathParams?: Record<string, unknown>;
  formData?: Record<string, unknown>;
};

/**
 * Generic HTTP API call helper.
 * Provide the full URL as apiId (e.g. "https://api.example.com/v1/resource").
 * For backward compatibility, apiId values that look like "Service/method"
 * are logged as warnings and return an empty object.
 */
export async function callDataApi(
  apiId: string,
  options: DataApiCallOptions = {}
): Promise<unknown> {
  // Detect legacy "Service/method" style calls and warn
  if (!apiId.startsWith("http")) {
    console.warn(
      `[DataApi] Legacy apiId format "${apiId}" is not supported. ` +
      "Replace with a direct HTTP call to the target API."
    );
    return {};
  }

  let url = apiId;
  if (options.pathParams) {
    for (const [k, v] of Object.entries(options.pathParams)) {
      url = url.replace(`{${k}}`, encodeURIComponent(String(v)));
    }
  }
  if (options.query) {
    const qs = new URLSearchParams(
      Object.entries(options.query).map(([k, v]) => [k, String(v)])
    );
    url = `${url}?${qs.toString()}`;
  }

  const response = await fetch(url, {
    method: options.body || options.formData ? "POST" : "GET",
    headers: { "content-type": "application/json" },
    ...(options.body ? { body: JSON.stringify(options.body) } : {}),
  });

  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    throw new Error(
      `Data API request failed (${response.status} ${response.statusText})${detail ? `: ${detail}` : ""}`
    );
  }
  return response.json().catch(() => ({}));
}
