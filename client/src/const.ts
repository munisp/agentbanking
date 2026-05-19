export { ONE_YEAR_MS } from "@shared/const";

/**
 * Returns the Keycloak login URL.
 * The backend /api/auth/login route initiates the Authorization Code flow.
 * An optional returnTo path is forwarded so the user lands back where they
 * started after a successful login.
 */
export const getLoginUrl = (returnTo?: string): string => {
  const path =
    returnTo ??
    (typeof window !== "undefined"
      ? window.location.pathname + window.location.search
      : "/");
  const params = new URLSearchParams();
  if (path && path !== "/") {
    params.set("returnTo", path);
  }
  const query = params.toString();
  return `/api/auth/login${query ? `?${query}` : ""}`;
};

/**
 * Returns the Keycloak logout URL.
 * The backend /api/auth/logout clears the session cookie and redirects
 * to the Keycloak end-session endpoint.
 */
export const getLogoutUrl = (): string => "/api/auth/logout";
